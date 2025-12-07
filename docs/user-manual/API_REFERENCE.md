# Rendiff API Reference

Complete reference documentation for all Rendiff API endpoints.

## Base URL

```
http://localhost:8000/api/v1
```

For production deployments with HTTPS:

```
https://your-domain.com/api/v1
```

## Authentication

All endpoints (except `/health`) require authentication when `ENABLE_API_KEYS=true`.

Include your API key in the `X-API-Key` header:

```bash
curl -H "X-API-Key: sk-your-api-key" https://api.example.com/api/v1/jobs
```

## Response Format

All responses are JSON with consistent structure:

### Success Response

```json
{
  "id": "uuid",
  "status": "string",
  "data": {}
}
```

### Error Response

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": {}
  }
}
```

## Rate Limits

| Tier | Requests/Hour | Burst |
|------|---------------|-------|
| Basic | 500 | 50 |
| Pro | 2,000 | 200 |
| Enterprise | 10,000 | 1,000 |

Rate limit headers are included in responses:

```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1642000000
```

---

## Health Endpoints

### GET /health

Check API and dependency health status.

**Authentication:** Not required

**Response:**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "healthy",
      "latency_ms": 2
    },
    "redis": {
      "status": "healthy",
      "latency_ms": 1
    },
    "ffmpeg": {
      "status": "healthy",
      "version": "6.1"
    },
    "storage": {
      "status": "healthy",
      "backends": ["local", "s3"]
    }
  }
}
```

**Status Values:**
- `healthy` - All systems operational
- `degraded` - Some systems have issues
- `unhealthy` - Critical systems failing

---

## Conversion Endpoints

### POST /convert

Create a new media conversion job.

**Request Body:**

```json
{
  "input_path": "local:///storage/input.mp4",
  "output_path": "local:///storage/output.webm",
  "operations": [
    {
      "type": "transcode",
      "video_codec": "vp9",
      "audio_codec": "opus",
      "crf": 23
    }
  ],
  "options": {
    "priority": "normal",
    "metadata": {
      "title": "My Video"
    }
  },
  "webhook_url": "https://example.com/webhook"
}
```

**Parameters:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `input_path` | string | Yes | Source file URI |
| `output_path` | string | Yes | Destination file URI |
| `operations` | array | No | Processing operations |
| `options` | object | No | Global options |
| `webhook_url` | string | No | Notification URL |

**Response (201 Created):**

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

**Error Responses:**

| Code | Description |
|------|-------------|
| 400 | Invalid request (validation error) |
| 401 | Missing or invalid API key |
| 429 | Rate limit exceeded |
| 500 | Internal server error |

---

## Operations Reference

### Transcode Operation

Convert video/audio codecs and adjust quality.

```json
{
  "type": "transcode",
  "video_codec": "h264",
  "audio_codec": "aac",
  "width": 1920,
  "height": 1080,
  "crf": 23,
  "preset": "medium",
  "video_bitrate": "5M",
  "audio_bitrate": "128k",
  "fps": 30
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `video_codec` | string | - | h264, h265, vp9, av1, copy |
| `audio_codec` | string | - | aac, mp3, opus, flac, copy |
| `width` | integer | - | Output width (must be even) |
| `height` | integer | - | Output height (must be even) |
| `crf` | integer | 23 | Quality (0-51, lower=better) |
| `preset` | string | medium | ultrafast to veryslow |
| `video_bitrate` | string | - | e.g., "5M", "2500k" |
| `audio_bitrate` | string | - | e.g., "128k", "320k" |
| `fps` | number | - | Frame rate (1-120) |

### Trim Operation

Extract a portion of the media file.

```json
{
  "type": "trim",
  "start": 60,
  "duration": 30
}
```

or

```json
{
  "type": "trim",
  "start": "1:00",
  "end": "1:30"
}
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `start` | number/string | Start time in seconds or HH:MM:SS |
| `duration` | number/string | Duration (if not using end) |
| `end` | number/string | End time (if not using duration) |

### Filter Operation

Apply video/audio filters.

```json
{
  "type": "filter",
  "name": "denoise",
  "params": {
    "strength": "medium"
  }
}
```

**Available Filters:**

| Filter | Description | Parameters |
|--------|-------------|------------|
| `denoise` | Reduce noise | `strength`: low/medium/high |
| `deinterlace` | Remove interlacing | - |
| `stabilize` | Stabilize shaky video | `strength`: 0.0-1.0 |
| `sharpen` | Sharpen video | `amount`: 0.0-2.0 |
| `blur` | Blur video | `radius`: 1-20 |
| `brightness` | Adjust brightness | `value`: -1.0 to 1.0 |
| `contrast` | Adjust contrast | `value`: 0.0 to 2.0 |
| `saturation` | Adjust saturation | `value`: 0.0 to 3.0 |

### Watermark Operation

Add image overlay to video.

```json
{
  "type": "watermark",
  "image": "local:///storage/logo.png",
  "position": "bottom-right",
  "opacity": 0.8,
  "scale": 0.1
}
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `image` | string | - | Watermark image URI |
| `position` | string | bottom-right | top-left, top-right, bottom-left, bottom-right, center |
| `opacity` | number | 0.8 | Opacity (0.0-1.0) |
| `scale` | number | 0.1 | Scale relative to video |

---

## Streaming Endpoints

### POST /stream

Create HLS or DASH streaming output.

**Request Body:**

```json
{
  "input_path": "local:///storage/input.mp4",
  "output_path": "local:///storage/stream/",
  "options": {
    "format": "hls",
    "segment_duration": 6,
    "variants": [
      {"height": 360, "bitrate": "800k"},
      {"height": 480, "bitrate": "1400k"},
      {"height": 720, "bitrate": "2800k"},
      {"height": 1080, "bitrate": "5000k"}
    ]
  }
}
```

**Parameters:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | string | hls | hls or dash |
| `segment_duration` | integer | 6 | Segment length in seconds |
| `variants` | array | - | Quality variants |

**Variant Parameters:**

| Field | Type | Description |
|-------|------|-------------|
| `height` | integer | Output height |
| `bitrate` | string | Target bitrate |
| `width` | integer | Output width (optional) |

---

## Analysis Endpoints

### POST /analyze

Analyze video quality metrics.

**Request Body:**

```json
{
  "reference_path": "local:///storage/original.mp4",
  "distorted_path": "local:///storage/compressed.mp4",
  "metrics": ["vmaf", "psnr", "ssim"]
}
```

**Response:**

```json
{
  "id": "job-id",
  "status": "completed",
  "results": {
    "vmaf": {
      "score": 95.234,
      "min": 89.5,
      "max": 98.7
    },
    "psnr": {
      "y": 42.5,
      "u": 48.2,
      "v": 49.1
    },
    "ssim": {
      "score": 0.987
    }
  }
}
```

---

## Job Management Endpoints

### GET /jobs

List all jobs for the authenticated API key.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | - | Filter by status |
| `page` | integer | 1 | Page number |
| `page_size` | integer | 20 | Items per page (max 100) |

**Response:**

```json
{
  "items": [
    {
      "id": "job-id-1",
      "status": "completed",
      "progress": 100.0,
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 42,
  "page": 1,
  "page_size": 20,
  "has_next": true,
  "has_prev": false
}
```

### GET /jobs/{id}

Get detailed job status.

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 67.5,
  "stage": "encoding",
  "fps": 45.2,
  "eta_seconds": 120,
  "input_path": "local:///storage/input.mp4",
  "output_path": "local:///storage/output.webm",
  "operations": [...],
  "created_at": "2025-01-15T10:30:00Z",
  "started_at": "2025-01-15T10:30:05Z",
  "worker_id": "worker-1"
}
```

### DELETE /jobs/{id}

Cancel a pending or processing job.

**Response (200 OK):**

```json
{
  "id": "job-id",
  "status": "cancelled",
  "message": "Job cancelled successfully"
}
```

**Error Responses:**

| Code | Description |
|------|-------------|
| 404 | Job not found |
| 409 | Job already completed/failed |

---

## Admin Endpoints

> Requires admin API key (configured via `ADMIN_API_KEYS`)

### POST /admin/api-keys

Create a new API key.

**Request:**

```json
{
  "name": "My Application",
  "description": "Production API key",
  "rate_limit": 2000,
  "expires_in_days": 365
}
```

**Response:**

```json
{
  "id": "key-id",
  "key": "sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "name": "My Application",
  "created_at": "2025-01-15T10:30:00Z",
  "expires_at": "2026-01-15T10:30:00Z"
}
```

### GET /admin/api-keys

List all API keys.

### DELETE /admin/api-keys/{id}

Revoke an API key.

### GET /admin/stats

Get system statistics.

**Response:**

```json
{
  "jobs": {
    "total": 10000,
    "pending": 5,
    "processing": 3,
    "completed": 9800,
    "failed": 192
  },
  "workers": {
    "active": 4,
    "idle": 2
  },
  "storage": {
    "used_bytes": 1099511627776,
    "backends": {
      "local": {"files": 500, "bytes": 549755813888},
      "s3": {"files": 200, "bytes": 549755813888}
    }
  }
}
```

---

## Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid request parameters |
| `AUTH_ERROR` | 401 | Authentication failed |
| `AUTHZ_ERROR` | 403 | Insufficient permissions |
| `NOT_FOUND` | 404 | Resource not found |
| `RATE_LIMIT_ERROR` | 429 | Too many requests |
| `PROCESSING_ERROR` | 500 | Processing failed |
| `STORAGE_ERROR` | 500 | Storage operation failed |
| `INTERNAL_ERROR` | 500 | Unexpected error |

---

## Webhooks

When a job completes, Rendiff sends a POST request to your webhook URL.

### Completion Webhook

```json
{
  "event": "job.completed",
  "timestamp": "2025-01-15T10:35:00Z",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "output_path": "local:///storage/output.webm",
  "processing_time": 300.5,
  "metrics": {
    "input_size": 104857600,
    "output_size": 52428800,
    "compression_ratio": 2.0
  }
}
```

### Failure Webhook

```json
{
  "event": "job.failed",
  "timestamp": "2025-01-15T10:35:00Z",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "failed",
  "error": "Processing failed"
}
```

---

## SDK Examples

### Python

```python
import requests

API_URL = "http://localhost:8000/api/v1"
API_KEY = "sk-your-api-key"

headers = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

# Create job
response = requests.post(
    f"{API_URL}/convert",
    headers=headers,
    json={
        "input_path": "local:///storage/input.mp4",
        "output_path": "local:///storage/output.webm",
        "operations": [
            {"type": "transcode", "video_codec": "vp9"}
        ]
    }
)

job = response.json()
print(f"Job created: {job['id']}")

# Poll for completion
import time
while True:
    status = requests.get(
        f"{API_URL}/jobs/{job['id']}",
        headers=headers
    ).json()

    if status["status"] in ["completed", "failed"]:
        break

    print(f"Progress: {status['progress']}%")
    time.sleep(5)
```

### JavaScript

```javascript
const API_URL = 'http://localhost:8000/api/v1';
const API_KEY = 'sk-your-api-key';

async function convertVideo() {
  // Create job
  const response = await fetch(`${API_URL}/convert`, {
    method: 'POST',
    headers: {
      'X-API-Key': API_KEY,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      input_path: 'local:///storage/input.mp4',
      output_path: 'local:///storage/output.webm',
      operations: [
        { type: 'transcode', video_codec: 'vp9' }
      ]
    })
  });

  const job = await response.json();
  console.log(`Job created: ${job.id}`);

  // Poll for completion
  while (true) {
    const status = await fetch(`${API_URL}/jobs/${job.id}`, {
      headers: { 'X-API-Key': API_KEY }
    }).then(r => r.json());

    if (['completed', 'failed'].includes(status.status)) {
      return status;
    }

    console.log(`Progress: ${status.progress}%`);
    await new Promise(r => setTimeout(r, 5000));
  }
}
```

### cURL

```bash
# Create conversion job
curl -X POST http://localhost:8000/api/v1/convert \
  -H "X-API-Key: sk-your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "input_path": "local:///storage/input.mp4",
    "output_path": "local:///storage/output.webm",
    "operations": [{"type": "transcode", "video_codec": "vp9"}]
  }'

# Check job status
curl http://localhost:8000/api/v1/jobs/JOB_ID \
  -H "X-API-Key: sk-your-api-key"
```
