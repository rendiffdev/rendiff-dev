# syntax=docker/dockerfile:1

# Build argument for Python version consistency across all containers
ARG PYTHON_VERSION=3.12.7

# Build stage with comprehensive dependencies
FROM python:${PYTHON_VERSION}-slim AS builder

# Build-time labels for traceability
LABEL stage=builder
LABEL python.version=${PYTHON_VERSION}
LABEL build.date="2024-01-01"

# Set environment variables for consistent builds
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install comprehensive build dependencies (CRITICAL FIX for psycopg2)
RUN apt-get update && apt-get install -y \
    # Compilation tools
    gcc \
    g++ \
    make \
    # Development headers for Python extensions
    python3-dev \
    # PostgreSQL development dependencies (FIXES psycopg2-binary issue)
    libpq-dev \
    postgresql-client \
    # SSL/TLS dependencies
    libssl-dev \
    libffi-dev \
    # Image processing dependencies
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    # System utilities
    git \
    curl \
    xz-utils \
    # Package management
    pkg-config \
    # Cleanup to reduce layer size
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create virtual environment with stable configuration
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip and essential tools to latest stable versions
RUN pip install --upgrade \
    pip==24.0 \
    setuptools==69.5.1 \
    wheel==0.43.0

# Copy requirements with validation
COPY requirements.txt /tmp/requirements.txt

# Validate requirements file exists and is readable
RUN test -f /tmp/requirements.txt && test -r /tmp/requirements.txt

# Install Python packages with comprehensive error handling
RUN pip install --no-cache-dir \
    --prefer-binary \
    --force-reinstall \
    --compile \
    -r /tmp/requirements.txt

# Verify critical packages are installed correctly
RUN python -c "import psycopg2; print('psycopg2:', psycopg2.__version__)" && \
    python -c "import fastapi; print('fastapi:', fastapi.__version__)" && \
    python -c "import sqlalchemy; print('sqlalchemy:', sqlalchemy.__version__)"

# Runtime stage with minimal footprint
FROM python:${PYTHON_VERSION}-slim AS runtime

# Runtime labels
LABEL stage=runtime
LABEL python.version=${PYTHON_VERSION}
LABEL app.name="rendiff"
LABEL app.component="api"
LABEL maintainer="rendiff-team"
LABEL version="1.0.0"
LABEL description="Rendiff Media Processing API (Powered by FFmpeg)"
LABEL org.opencontainers.image.source="https://github.com/rendiffdev/rendiff-dev"

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    # Security settings
    PYTHONHASHSEED=random \
    # Performance settings
    MALLOC_ARENA_MAX=2

# Install runtime dependencies only (no build tools)
RUN apt-get update && apt-get install -y \
    # PostgreSQL client and runtime libraries (NOT dev headers)
    libpq5 \
    postgresql-client \
    # SSL/TLS runtime libraries
    libssl3 \
    libffi8 \
    # Image processing runtime libraries
    libjpeg62-turbo \
    libpng16-16 \
    libwebp7 \
    # System utilities
    curl \
    xz-utils \
    netcat-openbsd \
    ca-certificates \
    tini \
    # Process and log management
    logrotate \
    procps \
    # Health monitoring
    htop \
    # Network utilities
    iputils-ping \
    # File utilities
    file \
    # Cleanup to minimize image size
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && apt-get autoremove -y

# Install FFmpeg using standardized script
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh && \
    /tmp/install-ffmpeg.sh && \
    rm /tmp/install-ffmpeg.sh && \
    # Verify FFmpeg installation
    ffmpeg -version | head -1

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Create app user with specific UID/GID for better security
RUN groupadd -r -g 1000 rendiff \
    && useradd -r -m -u 1000 -g rendiff -s /bin/bash rendiff

# Create application directories with proper ownership and permissions
RUN mkdir -p \
    /app \
    /app/logs \
    /app/temp \
    /app/metrics \
    /app/uploads \
    /app/cache \
    /storage \
    /config \
    /data \
    /tmp/rendiff \
    && chown -R rendiff:rendiff \
    /app \
    /storage \
    /config \
    /data \
    /tmp/rendiff \
    && chmod -R 755 /app \
    && chmod -R 775 /tmp/rendiff \
    && chmod -R 755 /storage \
    && chmod -R 755 /config

# Set working directory
WORKDIR /app

# Copy application code with proper ownership
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff storage/ /app/storage/
COPY --chown=rendiff:rendiff alembic/ /app/alembic/
COPY --chown=rendiff:rendiff alembic.ini /app/alembic.ini

# Copy scripts for setup and maintenance
COPY --chown=rendiff:rendiff scripts/ /app/scripts/

# Ensure scripts are executable
RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

# Set up log rotation
RUN echo '/app/logs/*.log {\n\
    daily\n\
    missingok\n\
    rotate 7\n\
    compress\n\
    delaycompress\n\
    notifempty\n\
    create 0644 rendiff rendiff\n\
}' > /etc/logrotate.d/rendiff-api

# Switch to non-root user for security
USER rendiff

# Verify Python environment
RUN python --version && \
    pip --version && \
    python -c "import sys; print('Python executable:', sys.executable)" && \
    python -c "import site; print('Python path:', site.getsitepackages())"

# Verify critical dependencies
RUN python -c "import psycopg2; import fastapi; import sqlalchemy; print('All critical dependencies verified')"

# Create health check script
USER root
RUN echo '#!/bin/bash\n\
set -e\n\
# Check if the application is responding\n\
curl -f http://localhost:8000/api/v1/health || exit 1\n\
# Check if Python process is running\n\
pgrep -f "python.*api" >/dev/null || exit 1\n\
echo "Health check passed"\n\
' > /usr/local/bin/health-check && \
    chmod +x /usr/local/bin/health-check

USER rendiff

# Expose ports
EXPOSE 8000
EXPOSE 9000

# Comprehensive health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD /usr/local/bin/health-check

# Add startup validation
RUN echo '#!/bin/bash\n\
echo "=== API Container Startup Validation ==="\n\
echo "Python version: $(python --version)"\n\
echo "Working directory: $(pwd)"\n\
echo "User: $(whoami)"\n\
echo "Environment: $ENVIRONMENT"\n\
echo "Virtual environment: $VIRTUAL_ENV"\n\
echo "Python path: $PYTHONPATH"\n\
echo "=========================================="\n\
' > /app/startup-check.sh && chmod +x /app/startup-check.sh

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command with startup validation
CMD ["/bin/bash", "-c", "/app/startup-check.sh && exec /app/scripts/docker-entrypoint.sh api"]