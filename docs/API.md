# Rendiff API Documentation

Complete API reference for the production-ready Rendiff service.

> **Powered by FFmpeg:** All media processing is handled by FFmpeg under the hood.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [API Key Management](#api-key-management)
4. [Core Endpoints](#core-endpoints)
5. [Job Management](#job-management)
6. [Error Handling](#error-handling)
7. [Examples](#examples)
8. [SDKs](#sdks)

## Overview

Rendiff provides a RESTful interface to FFmpeg's media processing capabilities with hardware acceleration support. 

> **💡 New to setup?** See the [Setup Guide](SETUP.md) for deployment instructions.

All API requests should be made to:

```
http://localhost:8000/api/v1
```

### Base URL Structure

- Development: `http://localhost:8000/api/v1`
- Production: `https://your-domain.com/api/v1` (Configure with your domain)

### HTTPS Configuration

For production deployments, HTTPS is strongly recommended. The API supports both self-signed certificates for testing and Let's Encrypt certificates for production.

#### Quick HTTPS Setup

1. **Interactive Setup**: Run the setup wizard and choose HTTPS options
   ```bash
   ./setup.sh --standard
   # Production setup includes HTTPS with self-signed certificates
   ```

2. **Certificate Management**:
   ```bash
   # Standard setup includes HTTPS with self-signed certificates
   ./setup.sh --standard
   
   # For custom certificates, edit traefik configuration
   # and place certificates in ./traefik/certs/
   ```

3. **Deploy with HTTPS**:
   ```bash
   # Production deployment with HTTPS enabled by default
   ./setup.sh --standard
   ```

#### SSL Certificate Management

- **Check deployment status**: `./setup.sh --status`
- **View Traefik logs**: `docker compose logs traefik`
- **Restart SSL services**: `docker compose restart traefik`
- **Certificate location**: `./traefik/certs/`

See the [SSL Management Guide](SETUP.md#httpssl-configuration) for detailed information.

---

## 📚 Documentation Navigation

| Guide | Description | When to Use |
|-------|-------------|-------------|
| **[🏠 Main README](../README.md)** | Project overview and quick start | Start here |
| **[🚀 Setup Guide](SETUP.md)** | Complete deployment guide | Setting up |
| **[🔧 API Reference](API.md)** | Detailed API documentation | **You are here** |
| **[📦 Installation Guide](INSTALLATION.md)** | Advanced installation options | Custom installs |
| **[🏭 Production Setup](SETUP.md#production-setup)** | Production best practices | Production setup |
| **[🛡️ HTTPS/SSL Configuration](SETUP.md#httpssl-configuration)** | Security configuration | Security hardening |

### Content Type

All requests and responses use JSON:
```
Content-Type: application/json
```

## Authentication

### API Key Authentication

Include your API key in the request header:

```http
X-API-Key: your-api-key-here
```

Or use Bearer token:

```http
Authorization: Bearer your-api-key-here
```

## API Key Management

### Overview

The FFmpeg API uses a dual API key system:
- **Admin API Keys**: System administration and management
- **Rendiff API Keys**: Client authentication for regular API access

### Managing API Keys

#### Generate New API Keys
```bash
# List current API keys
./scripts/manage-api-keys.sh list

# Generate new API keys
./scripts/manage-api-keys.sh generate

# Test API keys
./scripts/manage-api-keys.sh test
```

#### Security Operations
```bash
# Rotate all keys (security incident response)
./scripts/manage-api-keys.sh rotate

# Delete specific keys
./scripts/manage-api-keys.sh delete

# Export keys securely
./scripts/manage-api-keys.sh export
```

### API Key Types

#### Admin API Keys
- **Purpose**: Administrative access to management endpoints
- **Usage**: System monitoring, cleanup, configuration
- **Generation**: Automatically during setup
- **Access**: Admin endpoints (`/admin/*`)

#### Rendiff API Keys  
- **Purpose**: Client authentication for regular API operations
- **Usage**: Video processing, job submission, file operations
- **Generation**: Interactive setup or management script
- **Access**: All API endpoints (`/api/v1/*`)

### Key Security Best Practices

1. **Regular Rotation**: Rotate keys every 90 days
2. **Unique Keys**: Use different keys per client/application
3. **Secure Storage**: Store keys in environment variables
4. **Access Monitoring**: Monitor for unauthorized usage
5. **Immediate Rotation**: Rotate immediately if compromise suspected

### Authentication Examples

#### Using curl
```bash
# With API key header
curl -H "X-API-Key: your_api_key_here" \
     http://localhost:8000/api/v1/jobs

# With Bearer token
curl -H "Authorization: Bearer your_api_key_here" \
     http://localhost:8000/api/v1/jobs
```

#### Using Python requests
```python
import requests

headers = {"X-API-Key": "your_api_key_here"}
response = requests.get("http://localhost:8000/api/v1/jobs", headers=headers)
```

#### Using JavaScript fetch
```javascript
const headers = {
  'X-API-Key': 'your_api_key_here',
  'Content-Type': 'application/json'
};

fetch('http://localhost:8000/api/v1/jobs', { headers })
  .then(response => response.json())
  .then(data => console.log(data));
```

### Obtaining API Keys

For self-hosted installations, API keys are managed locally. By default, any non-empty key is accepted. In production, implement proper key management.

## Core Endpoints

### Convert Media

Universal endpoint for all media conversion operations.

```http
POST /api/v1/convert
```

#### Basic Conversion

```json
{
  "input": "/storage/input/video.mov",
  "output": "mp4"
}
```

#### Advanced Conversion

```json
{
  "input": {
    "path": "s3://bucket/input/video.mov",
    "credentials": "presigned"
  },
  "output": {
    "path": "/storage/output/final.mp4",
    "format": "mp4",
    "video": {
      "codec": "h264",
      "preset": "medium",
      "crf": 23,
      "resolution": "1920x1080",
      "fps": 30
    },
    "audio": {
      "codec": "aac",
      "bitrate": "192k",
      "channels": 2,
      "normalize": true
    }
  },
  "operations": [
    {
      "type": "trim",
      "start": 10,
      "duration": 60
    },
    {
      "type": "watermark",
      "image": "/storage/assets/logo.png",
      "position": "bottom-right",
      "opacity": 0.8
    }
  ],
  "options": {
    "priority": "high",
    "hardware_acceleration": "auto",
    "webhook_url": "https://your-app.com/webhook"
  }
}
```

#### Response

```json
{
  "job": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "priority": "high",
    "progress": 0,
    "stage": "queued",
    "created_at": "2025-01-27T10:00:00Z",
    "links": {
      "self": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
      "events": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/events",
      "logs": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/logs"
    }
  }
}
```

### Analyze Media

Analyze media files for quality metrics without conversion.

```http
POST /api/v1/analyze
```

```json
{
  "input": "/storage/input/video.mp4",
  "reference": "/storage/reference/original.mp4",
  "metrics": ["vmaf", "psnr", "ssim"]
}
```

### Create Streaming Format

Generate HLS or DASH streaming formats.

```http
POST /api/v1/stream
```

```json
{
  "input": "/storage/input/video.mp4",
  "output": "/storage/output/stream",
  "type": "hls",
  "variants": [
    {"resolution": "1080p", "bitrate": "5M"},
    {"resolution": "720p", "bitrate": "2.5M"},
    {"resolution": "480p", "bitrate": "1M"}
  ],
  "segment_duration": 6
}
```

### Estimate Job

Get time and resource estimates without creating a job.

```http
POST /api/v1/estimate
```

```json
{
  "input": "/storage/input/video.mp4",
  "output": "mp4",
  "operations": [{"type": "resize", "resolution": "4k"}]
}
```

Response:
```json
{
  "estimated": {
    "duration_seconds": 300,
    "output_size_bytes": 524288000
  },
  "resources": {
    "cpu_cores": 4,
    "memory_gb": 8,
    "gpu_required": false
  }
}
```

## Job Management

### List Jobs

```http
GET /api/v1/jobs?status=processing&page=1&per_page=20&sort=created_at:desc
```

Parameters:
- `status`: Filter by status (queued, processing, completed, failed, cancelled)
- `page`: Page number (default: 1)
- `per_page`: Items per page (default: 20, max: 100)
- `sort`: Sort field and order (e.g., "created_at:desc")

### Get Job Details

```http
GET /api/v1/jobs/{job_id}
```

Response:
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": 45.5,
  "stage": "encoding",
  "fps": 24.5,
  "eta_seconds": 180,
  "created_at": "2025-01-27T10:00:00Z",
  "started_at": "2025-01-27T10:01:00Z",
  "progress_details": {
    "percentage": 45.5,
    "stage": "encoding",
    "fps": 24.5,
    "quality": {
      "vmaf": 94.5,
      "psnr": 42.1
    }
  }
}
```

### Cancel Job

```http
DELETE /api/v1/jobs/{job_id}
```

### Stream Progress Events

Real-time progress updates via Server-Sent Events.

```http
GET /api/v1/jobs/{job_id}/events
```

Example events:
```
event: progress
data: {"percentage": 25.5, "stage": "encoding", "fps": 48.5, "eta_seconds": 240}

event: progress
data: {"percentage": 50.0, "stage": "encoding", "fps": 52.1, "eta_seconds": 120}

event: complete
data: {"status": "completed", "output_path": "/storage/output/final.mp4"}
```

### Get Job Logs

```http
GET /api/v1/jobs/{job_id}/logs?lines=100
```

## Error Handling

### Error Response Format

```json
{
  "error": {
    "type": "validation_error",
    "code": "INVALID_CODEC_FORMAT",
    "message": "Codec 'vp9' is incompatible with format 'mp4'",
    "details": {
      "field": "output.video.codec",
      "value": "vp9",
      "allowed": ["h264", "h265"],
      "suggestion": "Use 'webm' format or change codec to 'h264'"
    },
    "doc_url": "https://docs.rendiff.com/errors/INVALID_CODEC_FORMAT",
    "request_id": "req_8g4f5e3b2c0d"
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_INPUT` | Input file not found or invalid |
| `INVALID_OUTPUT` | Output path or format invalid |
| `CODEC_MISMATCH` | Codec incompatible with container |
| `INSUFFICIENT_RESOURCES` | Not enough resources to process |
| `QUOTA_EXCEEDED` | API quota limit reached |
| `JOB_NOT_FOUND` | Job ID does not exist |
| `ACCESS_DENIED` | No permission to access resource |

## Examples

### Example 1: Simple MP4 Conversion

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.avi",
    "output": "mp4"
  }'
```

### Example 2: Resize Video

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.mp4",
    "output": {
      "path": "/storage/output/video_720p.mp4",
      "video": {"resolution": "1280x720"}
    }
  }'
```

### Example 3: Extract Audio

```bash
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.mp4",
    "output": {
      "path": "/storage/output/audio.mp3",
      "format": "mp3"
    }
  }'
```

### Example 4: Create HLS Stream

```bash
curl -X POST http://localhost:8000/api/v1/stream \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/input/video.mp4",
    "output": "/storage/output/stream",
    "type": "hls",
    "variants": [
      {"resolution": "720p", "bitrate": "2M"},
      {"resolution": "480p", "bitrate": "1M"}
    ]
  }'
```

## API Client Examples

### Python Client

```python
import requests
import time

class FFmpegAPIClient:
    def __init__(self, api_key, base_url="http://localhost:8000"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
    
    def convert(self, input_path, output_format):
        response = requests.post(
            f"{self.base_url}/api/v1/convert",
            json={"input": input_path, "output": output_format},
            headers=self.headers
        )
        return response.json()
    
    def get_job_status(self, job_id):
        response = requests.get(
            f"{self.base_url}/api/v1/jobs/{job_id}",
            headers=self.headers
        )
        return response.json()

# Usage
client = FFmpegAPIClient(api_key="your-api-key")
job = client.convert("/storage/input/video.avi", "mp4")
print(f"Job ID: {job['job']['id']}")
```

### JavaScript Client

```javascript
class FFmpegAPIClient {
    constructor(apiKey, baseUrl = 'http://localhost:8000') {
        this.apiKey = apiKey;
        this.baseUrl = baseUrl;
        this.headers = {
            'X-API-Key': apiKey,
            'Content-Type': 'application/json'
        };
    }
    
    async convert(input, output) {
        const response = await fetch(`${this.baseUrl}/api/v1/convert`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({ input, output })
        });
        return response.json();
    }
    
    async getJobStatus(jobId) {
        const response = await fetch(`${this.baseUrl}/api/v1/jobs/${jobId}`, {
            headers: this.headers
        });
        return response.json();
    }
}

// Usage
const client = new FFmpegAPIClient('your-api-key');
const job = await client.convert('/storage/input/video.avi', 'mp4');
console.log(`Job ID: ${job.job.id}`);
```

### cURL Examples

Basic API usage with cURL commands.

## Rate Limiting

Default rate limits per API key:
- 10 requests/second
- 1000 requests/hour
- 10 concurrent jobs

Rate limits are configurable through environment variables and can be adjusted based on your API key tier.

## Webhooks

Configure webhooks to receive job updates:

```json
{
  "webhook_url": "https://your-app.com/webhook",
  "webhook_events": ["progress", "complete", "error"]
}
```

Webhook payload:
```json
{
  "event": "progress",
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2025-01-27T10:05:00Z",
  "data": {
    "percentage": 75.5,
    "stage": "encoding",
    "fps": 45.2
  }
}
```

## SSL Certificate Management

### Overview

The FFmpeg API provides comprehensive SSL/TLS certificate management for secure HTTPS communication. This includes support for both self-signed certificates (for development/testing) and Let's Encrypt certificates (for production).

### Certificate Types

#### Self-Signed Certificates
- **Use Case**: Development, testing, internal networks
- **Pros**: Quick setup, no external dependencies
- **Cons**: Browser warnings, not trusted by default
- **Generation**: `./scripts/manage-ssl.sh generate-self-signed your-domain.com`

#### Let's Encrypt Certificates
- **Use Case**: Production deployments with public domains
- **Pros**: Trusted by browsers, free, auto-renewal
- **Cons**: Requires public domain, rate limits
- **Generation**: `./scripts/manage-ssl.sh generate-letsencrypt your-domain.com admin@example.com`

### SSL Management Commands

#### Certificate Generation
```bash
# Generate self-signed certificate
./scripts/manage-ssl.sh generate-self-signed api.example.com

# Generate Let's Encrypt certificate (production)
./scripts/manage-ssl.sh generate-letsencrypt api.example.com admin@example.com

# Generate Let's Encrypt certificate (staging/testing)
./scripts/manage-ssl.sh generate-letsencrypt api.example.com admin@example.com --staging
```

#### Certificate Information
```bash
# List current certificates
./scripts/manage-ssl.sh list

# View certificate details
./scripts/manage-ssl.sh list
# Output shows:
# - Certificate type (self-signed/letsencrypt)
# - Domain name
# - Creation and expiration dates
# - Certificate validity status
```

#### Certificate Testing
```bash
# Basic SSL configuration test
./scripts/manage-ssl.sh test api.example.com

# Comprehensive validation (recommended)
./scripts/manage-ssl.sh validate api.example.com
```

The validation command performs a 10-point check:
1. Certificate file existence and permissions
2. Certificate content validation
3. Private key validation
4. Certificate-key pair matching
5. Certificate expiration check
6. Domain name validation (CN and SAN)
7. DNS resolution verification
8. Port connectivity test (80, 443)
9. Nginx configuration validation
10. Docker Compose configuration check

#### Certificate Renewal
```bash
# Renew certificates (automatically detects type)
./scripts/manage-ssl.sh renew

# Let's Encrypt certificates renew automatically via cron job
# Self-signed certificates are regenerated with new expiration
```

### HTTPS Deployment

#### Using Docker Compose
```bash
# Standard HTTP deployment
docker compose up -d

# HTTPS deployment with SSL certificates
docker compose -f docker compose.yml -f docker compose.https.yml up -d
```

#### Manual Nginx Configuration
If you prefer to manage Nginx separately:
```bash
# Copy SSL certificates to nginx directory
cp ./ssl/cert.pem ./nginx/ssl/
cp ./ssl/key.pem ./nginx/ssl/

# Use the provided nginx.conf for HTTPS
# Configuration includes:
# - HTTP to HTTPS redirects
# - SSL/TLS security headers
# - Rate limiting
# - Proxy configurations
```

### Security Best Practices

#### SSL/TLS Configuration
- **TLS Version**: TLS 1.2 and 1.3 only
- **Cipher Suites**: Modern, secure cipher suites
- **HSTS**: HTTP Strict Transport Security enabled
- **OCSP Stapling**: Enabled for performance
- **Security Headers**: X-Frame-Options, X-Content-Type-Options, etc.

#### Certificate Management
- **Regular Renewal**: Let's Encrypt certificates auto-renew every 60 days
- **Monitoring**: Certificate expiration alerts built-in
- **Backup**: Certificate information stored in `./ssl/cert_info.json`
- **Validation**: Regular validation recommended

#### Domain Requirements for Let's Encrypt
- **DNS Resolution**: Domain must resolve to your server's public IP
- **Port Access**: Ports 80 and 443 must be accessible from the internet
- **Rate Limits**: Let's Encrypt has rate limits (20 certificates per domain per week)
- **Validation**: HTTP-01 challenge used for domain validation

### Troubleshooting

#### Common Issues

**Certificate generation fails**:
```bash
# Check domain resolution
./scripts/manage-ssl.sh validate your-domain.com

# Verify ports are accessible
netstat -tulnp | grep :80
netstat -tulnp | grep :443
```

**Browser shows certificate warnings**:
- Self-signed certificates will always show warnings
- Check certificate domain matches the URL
- Verify certificate is not expired

**Let's Encrypt validation fails**:
- Ensure domain resolves to your server
- Check firewall allows ports 80 and 443
- Verify no other services are using port 80
- Use staging environment for testing

**Certificate renewal fails**:
```bash
# Check certificate status
./scripts/manage-ssl.sh list

# Manual renewal attempt
./scripts/manage-ssl.sh renew

# For Let's Encrypt, check logs
docker compose logs certbot
```

#### Log Files
- **SSL Management**: `./ssl/renewal.log`
- **Nginx**: Container logs via `docker compose logs nginx`
- **Let's Encrypt**: Container logs via `docker compose logs certbot`

### Integration with API

Once HTTPS is configured, all API endpoints are available via secure connections:

```bash
# HTTPS API calls
curl -H "X-API-Key: your-key" https://your-domain.com/api/v1/health
curl -H "X-API-Key: your-key" https://your-domain.com/api/v1/jobs
```

The API automatically redirects HTTP traffic to HTTPS when SSL is enabled.

## Support

- API Documentation: http://localhost:8000/docs
- OpenAPI Schema: http://localhost:8000/openapi.json
- Health Check: http://localhost:8000/api/v1/health
- Metrics: http://localhost:9090 (if monitoring enabled)

## Advanced Features

### Batch Processing

Process multiple files simultaneously with batch operations:

```bash
curl -X POST "http://localhost:8000/api/v1/batch" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "jobs": [
      {
        "input": "/storage/video1.mp4",
        "output": "/storage/output1.mp4",
        "operations": [{"type": "transcode", "params": {"video_codec": "h264"}}]
      },
      {
        "input": "/storage/video2.avi", 
        "output": "/storage/output2.webm",
        "operations": [{"type": "transcode", "params": {"video_codec": "vp9"}}]
      }
    ],
    "batch_name": "Daily Processing",
    "validate_files": true
  }'
```

### Enhanced Thumbnails

Create professional thumbnails with multiple options:

```bash
# Single high-quality thumbnail
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/video.mp4",
    "output": "/storage/thumb.jpg",
    "operations": [
      {
        "type": "thumbnail",
        "params": {
          "timestamp": 30,
          "width": 1920,
          "height": 1080,
          "quality": "high"
        }
      }
    ]
  }'

# Multiple thumbnails at intervals
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/video.mp4",
    "output": "/storage/thumbnails/",
    "operations": [
      {
        "type": "thumbnail_grid", 
        "params": {
          "rows": 3,
          "cols": 4,
          "width": 1280,
          "height": 720
        }
      }
    ]
  }'
```

### Adaptive Streaming

Generate HLS/DASH streams with multiple quality variants:

```bash
curl -X POST "http://localhost:8000/api/v1/stream" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/video.mp4",
    "output": "/storage/streams/",
    "type": "hls",
    "variants": [
      {"resolution": "1920x1080", "bitrate": "5000k", "name": "1080p"},
      {"resolution": "1280x720", "bitrate": "2500k", "name": "720p"},
      {"resolution": "854x480", "bitrate": "1000k", "name": "480p"}
    ],
    "segment_duration": 6
  }'
```

### Quality Analysis

Analyze video quality with industry-standard metrics:

```bash
curl -X POST "http://localhost:8000/api/v1/analyze" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/processed.mp4",
    "reference": "/storage/original.mp4",
    "metrics": ["vmaf", "psnr", "ssim"]
  }'
```

### Advanced Watermarking

Professional watermark placement with precise control:

```bash
curl -X POST "http://localhost:8000/api/v1/convert" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input": "/storage/video.mp4",
    "output": "/storage/watermarked.mp4",
    "operations": [
      {
        "type": "watermark",
        "params": {
          "watermark_path": "/storage/logo.png",
          "position": "bottom-right",
          "opacity": 0.8,
          "scale": 0.15
        }
      }
    ]
  }'
```

### Media File Security

All uploaded files are automatically validated for security:

- **Malware Detection**: Scans for malicious file signatures
- **MIME Type Validation**: Ensures files are legitimate media
- **Content Analysis**: Deep inspection with FFprobe
- **Size Limits**: Configurable per API key tier
- **Entropy Analysis**: Detects packed/encrypted content