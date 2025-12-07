# syntax=docker/dockerfile:1

# Build arguments for consistency and stability
ARG WORKER_TYPE=cpu
ARG PYTHON_VERSION=3.12.7

# Build stage with stable Python version
FROM python:${PYTHON_VERSION}-slim AS builder

# Install comprehensive build dependencies (fixes psycopg2 issue)
RUN apt-get update && apt-get install -y \
    # Compilation tools
    gcc \
    g++ \
    make \
    # Development headers for Python extensions
    python3-dev \
    # PostgreSQL development dependencies (CRITICAL FIX)
    libpq-dev \
    postgresql-client \
    # SSL/TLS dependencies
    libssl-dev \
    libffi-dev \
    # System utilities
    git \
    curl \
    xz-utils \
    pkg-config \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==24.* \
    && pip install --no-cache-dir -r requirements.txt

# Runtime stage - use NVIDIA CUDA base for GPU support
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runtime-gpu

# Set labels
LABEL maintainer="rendiff-team" \
      version="1.0" \
      description="Rendiff Worker - GPU (Powered by FFmpeg)" \
      org.opencontainers.image.source="https://github.com/rendiffdev/rendiff-dev"

# Install Python with consistent version
RUN apt-get update && apt-get install -y \
    software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update

# Install Python and runtime dependencies
RUN apt-get install -y \
    python3.12 \
    python3.12-venv \
    python3.12-dev \
    # PostgreSQL runtime libraries (not dev headers)
    libpq5 \
    postgresql-client \
    # SSL/TLS runtime libraries
    libssl3 \
    libffi8 \
    # System utilities
    curl \
    xz-utils \
    netcat-openbsd \
    ca-certificates \
    tini \
    # Process management
    procps \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install latest FFmpeg from BtbN/FFmpeg-Builds
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh \
    && /tmp/install-ffmpeg.sh \
    && rm /tmp/install-ffmpeg.sh

# Runtime stage - standard for CPU with stable Python version
FROM python:${PYTHON_VERSION}-slim AS runtime-cpu

# Set labels
LABEL maintainer="rendiff-team" \
      version="1.0" \
      description="Rendiff Worker - CPU (Powered by FFmpeg)" \
      org.opencontainers.image.source="https://github.com/rendiffdev/rendiff-dev"

# Install runtime dependencies (no build tools)
RUN apt-get update && apt-get install -y \
    # PostgreSQL runtime libraries (not dev headers)
    libpq5 \
    postgresql-client \
    # SSL/TLS runtime libraries
    libssl3 \
    libffi8 \
    # System utilities
    curl \
    xz-utils \
    netcat-openbsd \
    ca-certificates \
    tini \
    # Process management
    procps \
    # Cleanup
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Install latest FFmpeg from BtbN/FFmpeg-Builds
COPY docker/install-ffmpeg.sh /tmp/install-ffmpeg.sh
RUN chmod +x /tmp/install-ffmpeg.sh \
    && /tmp/install-ffmpeg.sh \
    && rm /tmp/install-ffmpeg.sh

# Select runtime based on build arg (ARG declared at top)
FROM runtime-${WORKER_TYPE} AS runtime

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user with specific UID/GID for better security
RUN groupadd -r -g 1000 rendiff \
    && useradd -r -m -u 1000 -g rendiff -s /bin/bash rendiff

# Create directories with proper permissions
RUN mkdir -p /app /storage /config /data /tmp/rendiff /app/logs \
    && chown -R rendiff:rendiff /app /storage /config /data /tmp/rendiff

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff worker/ /app/worker/
COPY --chown=rendiff:rendiff storage/ /app/storage/

# Copy scripts for setup and maintenance
COPY --chown=rendiff:rendiff scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Switch to non-root user
USER rendiff

# Set environment for GPU support
ENV NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES=${NVIDIA_DRIVER_CAPABILITIES:-video,compute,utility}

# Health check with better configuration
HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
    CMD celery -A worker.main inspect ping -t 10 || exit 1

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run the worker
CMD ["/app/scripts/docker-entrypoint.sh", "worker"]