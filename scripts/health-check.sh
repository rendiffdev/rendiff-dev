#!/bin/bash
# Comprehensive health check for Rendiff services

set -e

# Configuration
POSTGRES_HOST=${POSTGRES_HOST:-postgres}
POSTGRES_PORT=${POSTGRES_PORT:-5432}
POSTGRES_USER=${POSTGRES_USER:-rendiff_user}
POSTGRES_DB=${POSTGRES_DB:-rendiff}

REDIS_HOST=${REDIS_HOST:-redis}
REDIS_PORT=${REDIS_PORT:-6379}

API_HOST=${API_HOST:-localhost}
API_PORT=${API_PORT:-8000}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Health check functions
check_postgres() {
    log "Checking PostgreSQL health..."
    
    if pg_isready -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" >/dev/null 2>&1; then
        log "✅ PostgreSQL is responsive"
        
        # Check database connectivity
        if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;" >/dev/null 2>&1; then
            log "✅ PostgreSQL database connection successful"
            
            # Check table exists
            if psql -h "$POSTGRES_HOST" -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT count(*) FROM jobs;" >/dev/null 2>&1; then
                log "✅ Database schema is valid"
                return 0
            else
                warn "Database schema might be missing"
                return 1
            fi
        else
            error "Cannot connect to PostgreSQL database"
            return 1
        fi
    else
        error "PostgreSQL is not responsive"
        return 1
    fi
}

check_redis() {
    log "Checking Redis health..."
    
    if redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" ping >/dev/null 2>&1; then
        log "✅ Redis is responsive"
        
        # Check Redis info
        local redis_info=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" info server 2>/dev/null)
        if [ $? -eq 0 ]; then
            local redis_version=$(echo "$redis_info" | grep "redis_version:" | cut -d: -f2 | tr -d '\r')
            log "✅ Redis version: $redis_version"
            return 0
        else
            warn "Cannot get Redis info"
            return 1
        fi
    else
        error "Redis is not responsive"
        return 1
    fi
}

check_ffmpeg() {
    log "Checking FFmpeg installation..."
    
    if command -v ffmpeg >/dev/null 2>&1; then
        local ffmpeg_version=$(ffmpeg -version 2>/dev/null | head -n1)
        log "✅ FFmpeg available: $ffmpeg_version"
        
        if command -v ffprobe >/dev/null 2>&1; then
            log "✅ FFprobe available"
            return 0
        else
            error "FFprobe not found"
            return 1
        fi
    else
        error "FFmpeg not found"
        return 1
    fi
}

check_api() {
    log "Checking API health..."
    
    local health_url="http://$API_HOST:$API_PORT/api/v1/health"
    
    if curl -sf "$health_url" >/dev/null 2>&1; then
        log "✅ API health endpoint is responsive"
        
        # Get detailed health info
        local health_response=$(curl -s "$health_url" 2>/dev/null)
        if [ $? -eq 0 ]; then
            log "✅ API health check passed"
            echo "API Response: $health_response"
            return 0
        else
            warn "API health endpoint returned invalid response"
            return 1
        fi
    else
        error "API is not responsive at $health_url"
        return 1
    fi
}

check_storage() {
    log "Checking storage accessibility..."
    
    local storage_path="/storage"
    
    if [ -d "$storage_path" ]; then
        if [ -w "$storage_path" ]; then
            log "✅ Storage directory is writable"
            
            # Test file creation
            local test_file="$storage_path/.health_test_$(date +%s)"
            if echo "test" > "$test_file" 2>/dev/null; then
                rm -f "$test_file"
                log "✅ Storage write test successful"
                return 0
            else
                error "Cannot write to storage directory"
                return 1
            fi
        else
            error "Storage directory is not writable"
            return 1
        fi
    else
        error "Storage directory does not exist"
        return 1
    fi
}

check_genai() {
    log "Checking GenAI capabilities..."
    
    if [ "$GENAI_ENABLED" = "true" ]; then
        # Check GPU availability
        if command -v nvidia-smi >/dev/null 2>&1; then
            log "✅ nvidia-smi available"
            
            local gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader,nounits 2>/dev/null)
            if [ $? -eq 0 ]; then
                log "✅ GPU detected: $gpu_info"
                
                # Check CUDA runtime
                if python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')" 2>/dev/null; then
                    log "✅ CUDA runtime is functional"
                    return 0
                else
                    warn "CUDA runtime check failed"
                    return 1
                fi
            else
                warn "Cannot query GPU information"
                return 1
            fi
        else
            warn "nvidia-smi not available (CPU fallback will be used)"
            return 0
        fi
    else
        log "GenAI features are disabled"
        return 0
    fi
}

# System resource checks
check_resources() {
    log "Checking system resources..."
    
    # Check disk space
    local disk_usage=$(df /storage 2>/dev/null | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 90 ]; then
        warn "Storage disk usage is high: ${disk_usage}%"
    else
        log "✅ Storage disk usage: ${disk_usage}%"
    fi
    
    # Check memory usage
    local mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100.0}')
    if [ "$mem_usage" -gt 90 ]; then
        warn "Memory usage is high: ${mem_usage}%"
    else
        log "✅ Memory usage: ${mem_usage}%"
    fi
    
    return 0
}

# Main health check
main() {
    local check_type=${1:-all}
    local exit_code=0
    
    log "Starting health check (type: $check_type)..."
    
    case $check_type in
        "postgres"|"all")
            if \! check_postgres; then
                exit_code=1
            fi
            ;;
    esac
    
    case $check_type in
        "redis"|"all")
            if \! check_redis; then
                exit_code=1
            fi
            ;;
    esac
    
    case $check_type in
        "ffmpeg"|"all")
            if \! check_ffmpeg; then
                exit_code=1
            fi
            ;;
    esac
    
    case $check_type in
        "api"|"all")
            if \! check_api; then
                exit_code=1
            fi
            ;;
    esac
    
    case $check_type in
        "storage"|"all")
            if \! check_storage; then
                exit_code=1
            fi
            ;;
    esac
    
    case $check_type in
        "genai"|"all")
            if \! check_genai; then
                exit_code=1
            fi
            ;;
    esac
    
    case $check_type in
        "resources"|"all")
            if \! check_resources; then
                exit_code=1
            fi
            ;;
    esac
    
    if [ $exit_code -eq 0 ]; then
        log "🎉 All health checks passed\!"
    else
        error "❌ Some health checks failed"
    fi
    
    return $exit_code
}

# Run health check
main "$@"
EOF < /dev/null