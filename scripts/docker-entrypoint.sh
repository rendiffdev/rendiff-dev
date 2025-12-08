#!/bin/bash
# Docker entrypoint script for FFmpeg API
# Handles initialization and service startup

set -e

# Function to wait for service
wait_for_service() {
    local host=$1
    local port=$2
    local service=$3
    local timeout=${4:-60}

    echo "Waiting for $service at $host:$port..."
    for i in $(seq 1 $timeout); do
        if nc -z "$host" "$port" 2>/dev/null; then
            echo "$service is ready!"
            return 0
        fi
        echo "Waiting for $service... ($i/$timeout)"
        sleep 1
    done

    echo "ERROR: $service at $host:$port not available after $timeout seconds"
    return 1
}

# Function to run database migrations
run_migrations() {
    echo "Running database migrations..."

    # Wait for PostgreSQL
    wait_for_service postgres 5432 "PostgreSQL" 120

    # Run Alembic migrations
    if [ -f "alembic.ini" ]; then
        echo "Running Alembic migrations..."
        alembic upgrade head
        echo "Database migrations completed."
    else
        echo "No alembic.ini found, skipping migrations."
    fi
}

# Function to initialize storage
init_storage() {
    echo "Initializing storage directories..."

    # Create storage directories
    mkdir -p /storage/input /storage/output /storage/temp
    mkdir -p /app/logs /app/temp

    # Set permissions
    chmod 755 /storage/input /storage/output /storage/temp
    chmod 755 /app/logs /app/temp

    echo "Storage directories initialized."
}

# Function to validate environment
validate_environment() {
    echo "Validating environment..."

    # Check required environment variables
    if [ -z "$DATABASE_URL" ]; then
        echo "ERROR: DATABASE_URL environment variable is required"
        exit 1
    fi

    if [ -z "$REDIS_URL" ]; then
        echo "ERROR: REDIS_URL environment variable is required"
        exit 1
    fi

    # Check FFmpeg installation
    if ! command -v ffmpeg &> /dev/null; then
        echo "ERROR: FFmpeg is not installed"
        exit 1
    fi

    if ! command -v ffprobe &> /dev/null; then
        echo "ERROR: FFprobe is not installed"
        exit 1
    fi

    echo "Environment validation passed."
}

# Function to setup monitoring
setup_monitoring() {
    echo "Setting up monitoring..."

    # Create metrics directory
    mkdir -p /app/metrics

    # Setup log rotation if available and writable
    if command -v logrotate &> /dev/null; then
        echo "Setting up log rotation..."
        if [ -w /etc/logrotate.d ]; then
            cat > /etc/logrotate.d/rendiff << 'LOGROTATE_EOF'
/app/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    sharedscripts
}
LOGROTATE_EOF
        else
            echo "Skipping logrotate setup (permission denied)"
        fi
    fi

    echo "Monitoring setup completed."
}

# Main execution
main() {
    local service_type=${1:-api}

    echo "Starting FFmpeg API Docker Container..."
    echo "Service Type: $service_type"
    echo "Environment: ${ENVIRONMENT:-production}"

    # Initialize
    validate_environment
    init_storage
    setup_monitoring

    # Service-specific initialization
    case $service_type in
        "api")
            echo "Starting API service..."

            # Wait for dependencies
            wait_for_service postgres 5432 "PostgreSQL" 120
            wait_for_service redis 6379 "Redis" 60

            # Run migrations (API service is responsible for this)
            run_migrations

            # Start API server
            exec uvicorn api.main:app \
                --host 0.0.0.0 \
                --port ${API_PORT:-8000} \
                --workers ${API_WORKERS:-4} \
                --worker-class uvicorn.workers.UvicornWorker \
                --access-log \
                --log-level ${LOG_LEVEL:-info}
            ;;

        "worker")
            echo "Starting worker service..."

            # Wait for dependencies
            wait_for_service postgres 5432 "PostgreSQL" 120
            wait_for_service redis 6379 "Redis" 60

            # Start Celery worker
            exec celery -A worker.main worker \
                --loglevel=${LOG_LEVEL:-info} \
                --concurrency=${WORKER_CONCURRENCY:-4} \
                --prefetch-multiplier=${WORKER_PREFETCH_MULTIPLIER:-1} \
                --max-tasks-per-child=${WORKER_MAX_TASKS_PER_CHILD:-100} \
                --time-limit=${WORKER_TASK_TIME_LIMIT:-21600}
            ;;

        "migrate")
            echo "Running migration service..."
            run_migrations
            echo "Migration completed successfully."
            ;;

        "setup")
            echo "Running setup tasks..."
            validate_environment
            init_storage
            echo "Setup completed successfully."
            ;;

        *)
            echo "Unknown service type: $service_type"
            echo "Available service types: api, worker, migrate, setup"
            exit 1
            ;;
    esac
}

# Signal handlers for graceful shutdown
shutdown() {
    echo "Received shutdown signal..."

    # Kill child processes
    if [ ! -z "$!" ]; then
        kill -TERM "$!" 2>/dev/null || true
        wait "$!" 2>/dev/null || true
    fi

    echo "Shutdown completed."
    exit 0
}

# Setup signal handlers
trap shutdown SIGTERM SIGINT

# Run main function with all arguments
main "$@"
