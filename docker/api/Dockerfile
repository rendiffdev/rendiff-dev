# syntax=docker/dockerfile:1

# Build argument for Python version consistency across all containers
ARG PYTHON_VERSION=3.12.7

# ============================================================================
# STAGE 1: FFmpeg Downloader (CACHED - only rebuilds when FFmpeg needs update)
# ============================================================================
FROM debian:bookworm-slim AS ffmpeg-downloader

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download FFmpeg - this layer is cached until you change the URL
ARG TARGETARCH=amd64
RUN set -ex && \
    case "${TARGETARCH}" in \
        amd64) FFMPEG_ARCH="linux64" ;; \
        arm64) FFMPEG_ARCH="linuxarm64" ;; \
        *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    curl -fsSL -o /tmp/ffmpeg.tar.xz \
        "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-${FFMPEG_ARCH}-gpl.tar.xz" && \
    mkdir -p /ffmpeg && \
    tar -xf /tmp/ffmpeg.tar.xz -C /ffmpeg --strip-components=1 && \
    rm /tmp/ffmpeg.tar.xz && \
    chmod +x /ffmpeg/bin/*

# ============================================================================
# STAGE 2: Python Dependencies Builder
# ============================================================================
FROM python:${PYTHON_VERSION}-slim AS builder

LABEL stage=builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=100

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make python3-dev libpq-dev libssl-dev libffi-dev \
    libjpeg-dev libpng-dev libwebp-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Upgrade pip
RUN pip install --upgrade pip==24.0 setuptools==69.5.1 wheel==0.43.0

# Install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --prefer-binary -r /tmp/requirements.txt

# Verify critical packages
RUN python -c "import psycopg2; import fastapi; import sqlalchemy; print('Dependencies OK')"

# ============================================================================
# STAGE 3: Runtime Image
# ============================================================================
FROM python:${PYTHON_VERSION}-slim AS runtime

LABEL maintainer="rendiff-team" \
      version="1.0.0" \
      description="Rendiff Media Processing API (Powered by FFmpeg)"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONHASHSEED=random \
    MALLOC_ARENA_MAX=2

# Install runtime dependencies (minimal)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 postgresql-client libssl3 libffi8 \
    libjpeg62-turbo libpng16-16 libwebp7 \
    curl netcat-openbsd ca-certificates tini \
    procps file \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy FFmpeg from downloader stage (FAST - just copies cached binaries)
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffprobe /usr/local/bin/ffprobe
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    ffmpeg -version | head -1

# Copy Python virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Create app user
RUN groupadd -r -g 1000 rendiff && \
    useradd -r -m -u 1000 -g rendiff -s /bin/bash rendiff

# Create directories
RUN mkdir -p /app /app/logs /app/temp /app/metrics /app/uploads /app/cache \
    /storage /config /data /tmp/rendiff && \
    chown -R rendiff:rendiff /app /storage /config /data /tmp/rendiff && \
    chmod -R 755 /app /storage /config

WORKDIR /app

# Copy application code
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff worker/ /app/worker/
COPY --chown=rendiff:rendiff storage/ /app/storage/
COPY --chown=rendiff:rendiff alembic/ /app/alembic/
COPY --chown=rendiff:rendiff alembic.ini /app/alembic.ini
COPY --chown=rendiff:rendiff scripts/ /app/scripts/

RUN chmod +x /app/scripts/*.sh 2>/dev/null || true

# Switch to non-root user
USER rendiff

# Verify setup
RUN python --version && pip --version && \
    python -c "import psycopg2; import fastapi; import sqlalchemy; print('All dependencies OK')"

# Health check script
USER root
RUN echo '#!/bin/bash\ncurl -f http://localhost:8000/api/v1/health || exit 1' > /usr/local/bin/health-check && \
    chmod +x /usr/local/bin/health-check
USER rendiff

EXPOSE 8000
EXPOSE 9000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=5 \
    CMD /usr/local/bin/health-check

# Startup script
RUN echo '#!/bin/bash\necho "=== API Container Ready ==="\necho "Python: $(python --version)"\necho "FFmpeg: $(ffmpeg -version 2>&1 | head -1)"\n' > /app/startup-check.sh && \
    chmod +x /app/startup-check.sh

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/bin/bash", "-c", "/app/startup-check.sh && exec /app/scripts/docker-entrypoint.sh api"]
