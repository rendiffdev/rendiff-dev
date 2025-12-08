# syntax=docker/dockerfile:1

# Build arguments
ARG WORKER_TYPE=cpu
ARG PYTHON_VERSION=3.12.7

# ============================================================================
# STAGE 1: FFmpeg Downloader (CACHED - only rebuilds when FFmpeg needs update)
# ============================================================================
FROM debian:bookworm-slim AS ffmpeg-downloader

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download FFmpeg - this layer is cached
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

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make python3-dev libpq-dev libssl-dev libffi-dev pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python packages
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip==24.0 && \
    pip install --no-cache-dir --prefer-binary -r /tmp/requirements.txt

# ============================================================================
# STAGE 3a: GPU Runtime Base (NVIDIA CUDA)
# ============================================================================
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04 AS runtime-gpu

LABEL maintainer="rendiff-team" \
      version="1.0" \
      description="Rendiff Worker - GPU (Powered by FFmpeg)"

# Install Python 3.12 on Ubuntu
RUN apt-get update && apt-get install -y --no-install-recommends \
    software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    python3.12 python3.12-venv python3.12-dev \
    libpq5 postgresql-client libssl3 libffi8 \
    curl netcat-openbsd ca-certificates tini procps \
    && rm -rf /var/lib/apt/lists/*

# Copy FFmpeg from downloader (FAST)
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffprobe /usr/local/bin/ffprobe
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# ============================================================================
# STAGE 3b: CPU Runtime Base (Python slim)
# ============================================================================
FROM python:${PYTHON_VERSION}-slim AS runtime-cpu

LABEL maintainer="rendiff-team" \
      version="1.0" \
      description="Rendiff Worker - CPU (Powered by FFmpeg)"

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 postgresql-client libssl3 libffi8 \
    curl netcat-openbsd ca-certificates tini procps \
    && rm -rf /var/lib/apt/lists/*

# Copy FFmpeg from downloader (FAST)
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffprobe /usr/local/bin/ffprobe
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# ============================================================================
# STAGE 4: Final Runtime (selects GPU or CPU based on WORKER_TYPE)
# ============================================================================
FROM runtime-${WORKER_TYPE} AS runtime

# Copy Python virtual environment
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Create app user
RUN groupadd -r -g 1000 rendiff && \
    useradd -r -m -u 1000 -g rendiff -s /bin/bash rendiff

# Create directories
RUN mkdir -p /app /storage /config /data /tmp/rendiff /app/logs && \
    chown -R rendiff:rendiff /app /storage /config /data /tmp/rendiff

WORKDIR /app

# Copy application code
COPY --chown=rendiff:rendiff api/ /app/api/
COPY --chown=rendiff:rendiff worker/ /app/worker/
COPY --chown=rendiff:rendiff storage/ /app/storage/
COPY --chown=rendiff:rendiff scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Switch to non-root user
USER rendiff

# Verify FFmpeg
RUN ffmpeg -version | head -1

# GPU environment (only used when WORKER_TYPE=gpu)
ENV NVIDIA_VISIBLE_DEVICES=${NVIDIA_VISIBLE_DEVICES:-all}
ENV NVIDIA_DRIVER_CAPABILITIES=${NVIDIA_DRIVER_CAPABILITIES:-video,compute,utility}

HEALTHCHECK --interval=60s --timeout=30s --start-period=120s --retries=3 \
    CMD celery -A worker.main inspect ping -t 10 || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/scripts/docker-entrypoint.sh", "worker"]
