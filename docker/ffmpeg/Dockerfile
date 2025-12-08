# syntax=docker/dockerfile:1

# FFmpeg Base Image - Build once, reuse everywhere
# This image contains only FFmpeg binaries and can be cached/pushed to registry

ARG FFMPEG_VERSION=latest

FROM debian:bookworm-slim AS ffmpeg-downloader

# Install download tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Download FFmpeg based on architecture
ARG TARGETARCH
RUN set -ex && \
    case "${TARGETARCH}" in \
        amd64) FFMPEG_ARCH="linux64" ;; \
        arm64) FFMPEG_ARCH="linuxarm64" ;; \
        *) echo "Unsupported arch: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    DOWNLOAD_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-${FFMPEG_ARCH}-gpl.tar.xz" && \
    echo "Downloading FFmpeg from: ${DOWNLOAD_URL}" && \
    curl -fsSL -o /tmp/ffmpeg.tar.xz "${DOWNLOAD_URL}" && \
    mkdir -p /ffmpeg && \
    tar -xf /tmp/ffmpeg.tar.xz -C /ffmpeg --strip-components=1 && \
    rm /tmp/ffmpeg.tar.xz

# Minimal FFmpeg image
FROM scratch AS ffmpeg-binaries
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffmpeg /ffmpeg
COPY --from=ffmpeg-downloader /ffmpeg/bin/ffprobe /ffprobe

# Verification stage
FROM debian:bookworm-slim AS verify
COPY --from=ffmpeg-binaries /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-binaries /ffprobe /usr/local/bin/ffprobe
RUN chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe && \
    ffmpeg -version && \
    ffprobe -version

# Final minimal image with just binaries
FROM scratch
COPY --from=ffmpeg-binaries /ffmpeg /usr/local/bin/ffmpeg
COPY --from=ffmpeg-binaries /ffprobe /usr/local/bin/ffprobe
