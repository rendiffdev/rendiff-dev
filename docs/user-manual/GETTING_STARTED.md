# Getting Started with Rendiff

This guide walks you through deploying Rendiff and making your first API calls.

## Prerequisites

Before starting, ensure you have:

- **Docker** 20.10 or later
- **Docker Compose** 2.0 or later
- **curl** or similar HTTP client (for testing)

Verify Docker is installed:

```bash
docker --version
# Docker version 24.x.x

docker compose version
# Docker Compose version v2.x.x
```

## Step 1: Deploy Rendiff

### Option A: Quick Development Setup

For local development and testing:

```bash
# Clone the repository
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Start with development configuration
./setup.sh --development
```

This starts Rendiff with:
- SQLite database (no PostgreSQL needed)
- Single API worker
- Debug mode enabled
- No authentication required

### Option B: Production Setup

For production deployments:

```bash
# Clone the repository
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Start with production configuration
docker compose -f compose.prod.yml up -d
```

This includes:
- PostgreSQL database
- Redis queue
- Multiple workers
- Monitoring (Prometheus/Grafana)
- SSL via Traefik

### Verify Deployment

Check that all services are running:

```bash
# Check service status
docker compose ps

# Check API health
curl http://localhost:8000/api/v1/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "ffmpeg": {"status": "healthy"}
  }
}
```

## Step 2: Understand Storage URIs

Rendiff uses storage URIs to specify file locations:

| URI Format | Description | Example |
|------------|-------------|---------|
| `local://` | Local filesystem | `local:///storage/video.mp4` |
| `s3://` | Amazon S3 | `s3://bucket/path/video.mp4` |
| `azure://` | Azure Blob | `azure://container/video.mp4` |
| `gcs://` | Google Cloud | `gcs://bucket/video.mp4` |

For this guide, we'll use local storage.

### Prepare a Test File

Place a test video file in the storage directory:

```bash
# Create storage directory
mkdir -p storage

# Copy a test file (or download a sample)
cp /path/to/your/video.mp4 storage/input.mp4

# Verify the file is accessible
ls -la storage/
```

## Step 3: Create Your First Job

### Basic Conversion

Convert a video to WebM format:

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/output.webm",
    "operations": [
      {
        "type": "transcode",
        "video_codec": "vp9",
        "audio_codec": "opus"
      }
    ]
  }'
```

Response:

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "progress": 0.0,
  "input_path": "local:///storage/input.mp4",
  "output_path": "local:///storage/output.webm",
  "created_at": "2025-01-15T10:30:00Z"
}
```

Save the job `id` for the next step.

### Check Job Status

Poll the job status until completion:

```bash
# Replace with your job ID
JOB_ID="550e8400-e29b-41d4-a716-446655440000"

curl http://localhost:8000/api/v1/jobs/$JOB_ID
```

Responses during processing:

```json
// Processing
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45.5,
  "stage": "encoding"
}

// Completed
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "progress": 100.0,
  "completed_at": "2025-01-15T10:32:45Z",
  "processing_time": 165.3
}
```

### Verify Output

Check that the output file was created:

```bash
ls -la storage/output.webm
```

## Step 4: Common Operations

### Trim a Video

Extract a 30-second clip starting at 1 minute:

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/clip.mp4",
    "operations": [
      {
        "type": "trim",
        "start": 60,
        "duration": 30
      }
    ]
  }'
```

### Change Resolution

Resize video to 720p:

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/720p.mp4",
    "operations": [
      {
        "type": "transcode",
        "video_codec": "h264",
        "width": 1280,
        "height": 720
      }
    ]
  }'
```

### Adjust Quality

Use CRF (Constant Rate Factor) for quality control:

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/highquality.mp4",
    "operations": [
      {
        "type": "transcode",
        "video_codec": "h264",
        "crf": 18,
        "preset": "slow"
      }
    ]
  }'
```

CRF values: 0 (lossless) to 51 (worst). Recommended: 18-23.

### Generate HLS Stream

Create adaptive streaming output:

```bash
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/stream/",
    "options": {
      "format": "hls",
      "variants": [
        {"height": 360, "bitrate": "800k"},
        {"height": 480, "bitrate": "1400k"},
        {"height": 720, "bitrate": "2800k"},
        {"height": 1080, "bitrate": "5000k"}
      ]
    }
  }'
```

### Analyze Video Quality

Measure VMAF, PSNR, and SSIM:

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "reference_path": "local:///storage/original.mp4",
    "distorted_path": "local:///storage/compressed.mp4",
    "metrics": ["vmaf", "psnr", "ssim"]
  }'
```

## Step 5: Use Webhooks (Optional)

Receive notifications when jobs complete:

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/output.mp4",
    "webhook_url": "https://your-server.com/webhook",
    "operations": [
      {"type": "transcode", "video_codec": "h264"}
    ]
  }'
```

Webhook payload on completion:

```json
{
  "event": "job.completed",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "output_path": "local:///storage/output.mp4",
  "processing_time": 120.5,
  "metrics": {
    "vmaf": 95.2
  }
}
```

## Step 6: Enable Authentication (Production)

For production, enable API key authentication:

### Generate an API Key

```bash
# Using the admin endpoint (requires ADMIN_API_KEYS environment variable)
curl -X POST http://localhost:8000/api/v1/admin/api-keys \
  -H "X-API-Key: your-admin-key" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Application",
    "rate_limit": 1000
  }'
```

Response:

```json
{
  "id": "key-id",
  "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "name": "My Application"
}
```

**Important:** Save the `key` value immediately. It won't be shown again.

### Use the API Key

Include the key in all requests:

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "X-API-Key: sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" \
  -H "Content-Type: application/json" \
  -d '{...}'
```

## Step 7: Monitor Jobs

### List All Jobs

```bash
curl http://localhost:8000/api/v1/jobs
```

### Filter by Status

```bash
# Get only processing jobs
curl "http://localhost:8000/api/v1/jobs?status=processing"

# Get failed jobs
curl "http://localhost:8000/api/v1/jobs?status=failed"
```

### Cancel a Job

```bash
curl -X DELETE http://localhost:8000/api/v1/jobs/JOB_ID
```

## Next Steps

Now that you have Rendiff running:

1. **Read the [API Reference](./API_REFERENCE.md)** for complete endpoint documentation
2. **Configure [Storage Backends](./STORAGE.md)** for cloud storage (S3, Azure, GCS)
3. **Set up [Authentication](./AUTHENTICATION.md)** for production
4. **Review [Configuration](./CONFIGURATION.md)** for tuning options
5. **Check [Troubleshooting](./TROUBLESHOOTING.md)** if you encounter issues

## Quick Reference

### Job Statuses

| Status | Description |
|--------|-------------|
| `pending` | Job created, waiting for worker |
| `processing` | Currently being processed |
| `completed` | Successfully finished |
| `failed` | Processing failed |
| `cancelled` | Cancelled by user |

### Video Codecs

| Codec | Description | Use Case |
|-------|-------------|----------|
| `h264` | H.264/AVC | Broad compatibility |
| `h265` | H.265/HEVC | Better compression |
| `vp9` | VP9 | Web (WebM) |
| `av1` | AV1 | Best compression |

### Presets (Speed vs Quality)

| Preset | Speed | Quality | Use Case |
|--------|-------|---------|----------|
| `ultrafast` | Fastest | Lowest | Testing |
| `fast` | Fast | Low | Real-time |
| `medium` | Balanced | Medium | Default |
| `slow` | Slow | High | Quality |
| `veryslow` | Slowest | Highest | Archival |
