# Rendiff User Manual

Welcome to the Rendiff User Manual. This guide provides everything you need to deploy, configure, and use Rendiff for your media processing needs.

> **About Rendiff:** Rendiff is a production-ready REST API for media processing, powered by [FFmpeg](https://ffmpeg.org/). It enables you to transcode, analyze, and stream video/audio files through a simple HTTP interface.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Getting Started](./GETTING_STARTED.md) | Quick start guide and first API call |
| [Installation](./INSTALLATION.md) | Deployment options and setup |
| [Configuration](./CONFIGURATION.md) | Environment variables and settings |
| [API Reference](./API_REFERENCE.md) | Complete endpoint documentation |
| [Authentication](./AUTHENTICATION.md) | API keys and security |
| [Storage Backends](./STORAGE.md) | File storage configuration |
| [Webhooks](./WEBHOOKS.md) | Event notifications |
| [Troubleshooting](./TROUBLESHOOTING.md) | Common issues and solutions |

## Quick Overview

### What Can Rendiff Do?

| Feature | Description |
|---------|-------------|
| **Transcode** | Convert between video/audio formats (H.264, H.265, VP9, AV1) |
| **Quality Analysis** | Measure VMAF, PSNR, SSIM scores |
| **Streaming** | Generate HLS and DASH adaptive streams |
| **Trim/Cut** | Extract segments from media files |
| **Filters** | Apply denoise, sharpen, stabilize effects |
| **Batch Processing** | Process multiple files concurrently |

### Supported Formats

**Video Input:** MP4, AVI, MOV, MKV, WebM, FLV, WMV, MPEG, TS
**Video Output:** MP4, WebM, MKV, HLS, DASH
**Audio Input:** MP3, WAV, FLAC, AAC, OGG, WMA, M4A
**Audio Output:** MP3, AAC, FLAC, WAV, OGG

### Architecture Overview

```
Your Application ──► Rendiff API ──► FFmpeg ──► Output Files
        │                │
        │                ▼
        │          Job Queue (Redis)
        │                │
        │                ▼
        │          Worker (Processing)
        │                │
        ◄────────────────┘
       Webhook Notification
```

## Getting Started in 5 Minutes

### 1. Deploy Rendiff

```bash
# Clone the repository
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Start all services
docker compose up -d

# Verify it's running
curl http://localhost:8000/api/v1/health
```

### 2. Create Your First Job

```bash
# Submit a conversion job
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/output.webm",
    "operations": [
      {"type": "transcode", "video_codec": "vp9", "audio_codec": "opus"}
    ]
  }'

# Response:
# {"id": "550e8400-e29b-41d4-a716-446655440000", "status": "pending", ...}
```

### 3. Check Job Status

```bash
curl http://localhost:8000/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000

# Response:
# {"id": "...", "status": "completed", "progress": 100.0, ...}
```

See [Getting Started](./GETTING_STARTED.md) for a complete walkthrough.

## System Requirements

### Minimum Requirements

| Resource | Requirement |
|----------|-------------|
| CPU | 4 cores |
| RAM | 8 GB |
| Storage | 50 GB SSD |
| Docker | 20.10+ |

### Recommended for Production

| Resource | Recommendation |
|----------|---------------|
| CPU | 8+ cores (16+ for 4K) |
| RAM | 32 GB (64 GB for 4K/8K) |
| GPU | NVIDIA RTX/Quadro (optional) |
| Storage | 500 GB+ NVMe SSD |
| Network | 1 Gbps+ |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Health check |
| `/api/v1/convert` | POST | Create conversion job |
| `/api/v1/analyze` | POST | Create analysis job |
| `/api/v1/stream` | POST | Create streaming job |
| `/api/v1/jobs` | GET | List jobs |
| `/api/v1/jobs/{id}` | GET | Get job status |
| `/api/v1/jobs/{id}` | DELETE | Cancel job |

See [API Reference](./API_REFERENCE.md) for complete documentation.

## Configuration Quick Reference

### Essential Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host:5432/rendiff

# Redis
REDIS_URL=redis://host:6379/0

# Security
ENABLE_API_KEYS=true
ADMIN_API_KEYS=your-admin-key

# Processing
MAX_CONCURRENT_JOBS=10
WORKER_CONCURRENCY=4
```

See [Configuration](./CONFIGURATION.md) for all options.

## Support

- **Documentation:** You're reading it!
- **Issues:** [GitHub Issues](https://github.com/rendiffdev/rendiff-dev/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rendiffdev/rendiff-dev/discussions)

## License

Rendiff is licensed under the MIT License.

**FFmpeg Notice:** Rendiff uses FFmpeg for media processing. FFmpeg is licensed under LGPL/GPL. See [ffmpeg.org/legal.html](https://ffmpeg.org/legal.html) for details.
