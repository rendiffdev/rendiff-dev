#!/bin/bash
# Install latest FFmpeg from BtbN/FFmpeg-Builds (static builds)
# This ensures we get the latest FFmpeg with all codecs enabled

set -e

echo "Installing FFmpeg..."

# Detect architecture
ARCH=$(uname -m)
case $ARCH in
    x86_64)
        FFMPEG_ARCH="linux64"
        DOWNLOAD_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz"
        ;;
    aarch64|arm64)
        FFMPEG_ARCH="linuxarm64"
        DOWNLOAD_URL="https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz"
        ;;
    *)
        echo "Unsupported architecture: $ARCH"
        exit 1
        ;;
esac

# Create temporary directory
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

echo "Downloading FFmpeg for $ARCH from $DOWNLOAD_URL..."
curl -L -o ffmpeg.tar.xz "$DOWNLOAD_URL"

echo "Extracting FFmpeg..."
tar -xf ffmpeg.tar.xz --strip-components=1

echo "Installing FFmpeg..."
cp bin/ffmpeg /usr/local/bin/
cp bin/ffprobe /usr/local/bin/
chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# Verify installation
echo "Verifying FFmpeg installation..."
ffmpeg -version
ffprobe -version

# Cleanup
cd /
rm -rf "$TEMP_DIR"

echo "FFmpeg installation completed successfully!"
