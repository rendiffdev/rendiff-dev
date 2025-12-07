# Configuration Guide

This guide covers all configuration options for Rendiff, including environment variables, storage backends, and performance tuning.

## Configuration Methods

Rendiff can be configured using:

1. **Environment variables** (highest priority)
2. **`.env` file** in the project root
3. **Default values** (lowest priority)

## Quick Start Configuration

Create a `.env` file based on the template:

```bash
cp .env.example .env
```

Edit the file with your settings:

```bash
# Minimal production configuration
DATABASE_URL=postgresql://rendiff_user:secure_password@postgres:5432/rendiff
REDIS_URL=redis://redis:6379/0
ENABLE_API_KEYS=true
ADMIN_API_KEYS=your-admin-key-here
```

---

## Core Settings

### Application

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode (shows docs, detailed errors) |
| `TESTING` | `false` | Enable test mode |
| `VERSION` | `1.0.0` | Application version |

### API Server

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Listen address |
| `API_PORT` | `8000` | Listen port |
| `API_WORKERS` | `4` | Number of uvicorn workers |
| `API_LOG_LEVEL` | `info` | Log level (debug, info, warning, error) |
| `API_RELOAD` | `false` | Enable auto-reload (development) |

**Example:**

```bash
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=8
API_LOG_LEVEL=info
```

---

## Database Configuration

### PostgreSQL (Recommended)

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | - | PostgreSQL connection string |
| `DATABASE_POOL_SIZE` | `20` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | `40` | Max overflow connections |
| `DATABASE_POOL_TIMEOUT` | `30` | Connection timeout (seconds) |

**Connection String Format:**

```
postgresql://username:password@host:port/database
```

**Example:**

```bash
DATABASE_URL=postgresql://rendiff_user:secure_password@postgres:5432/rendiff
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
```

### SQLite (Development Only)

```bash
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db
```

> **Warning:** SQLite does not support concurrent writes. Use PostgreSQL for production.

---

## Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `REDIS_MAX_CONNECTIONS` | `100` | Maximum connections |

**URL Format:**

```
redis://[:password@]host:port/db
```

**Examples:**

```bash
# Without password
REDIS_URL=redis://redis:6379/0

# With password
REDIS_URL=redis://:your_password@redis:6379/0

# Redis Cluster
REDIS_URL=redis://node1:6379,node2:6379,node3:6379/0
```

---

## Security Configuration

### API Key Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_API_KEYS` | `true` | Require API keys |
| `ADMIN_API_KEYS` | - | Comma-separated admin keys |
| `API_KEY_LENGTH` | `32` | Generated key length |
| `API_KEY_EXPIRY_DAYS` | `365` | Default key expiration |

**Example:**

```bash
ENABLE_API_KEYS=true
ADMIN_API_KEYS=sk-admin-key-1,sk-admin-key-2
```

### Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_CALLS` | `100` | Requests per period |
| `RATE_LIMIT_PERIOD` | `3600` | Period in seconds |
| `CONVERT_RATE_LIMIT` | `200` | /convert endpoint limit |
| `ANALYZE_RATE_LIMIT` | `100` | /analyze endpoint limit |
| `STREAM_RATE_LIMIT` | `50` | /stream endpoint limit |

**Example:**

```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_CALLS=1000
RATE_LIMIT_PERIOD=3600
```

### CORS and Security Headers

| Variable | Default | Description |
|----------|---------|-------------|
| `API_CORS_ORIGINS` | `*` | Allowed origins (comma-separated) |
| `API_TRUSTED_HOSTS` | `*` | Trusted hosts |
| `ENABLE_SECURITY_HEADERS` | `true` | Add security headers |

**Example:**

```bash
# Restrict to specific origins
API_CORS_ORIGINS=https://app.example.com,https://admin.example.com

# Multiple trusted hosts
API_TRUSTED_HOSTS=api.example.com,*.example.com
```

### IP Whitelisting

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_IP_WHITELIST` | `false` | Enable IP filtering |
| `IP_WHITELIST` | - | Allowed IPs/CIDRs |

**Example:**

```bash
ENABLE_IP_WHITELIST=true
IP_WHITELIST=10.0.0.0/8,192.168.0.0/16,203.0.113.0/24
```

---

## Storage Configuration

### Storage Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `STORAGE_CONFIG` | `/app/config/storage.yml` | Storage config file |
| `STORAGE_PATH` | `./storage` | Default storage directory |
| `TEMP_PATH` | `/tmp/rendiff` | Temporary files directory |

### Storage Configuration File

Create `config/storage.yml`:

```yaml
# Default backend for URI without prefix
default_backend: local

backends:
  # Local filesystem
  local:
    type: local
    base_path: /storage

  # AWS S3
  s3:
    type: s3
    bucket: my-rendiff-bucket
    region: us-east-1
    access_key: ${AWS_ACCESS_KEY_ID}
    secret_key: ${AWS_SECRET_ACCESS_KEY}

  # Azure Blob Storage
  azure:
    type: azure
    container: rendiff-container
    connection_string: ${AZURE_STORAGE_CONNECTION_STRING}

  # Google Cloud Storage
  gcs:
    type: gcs
    bucket: my-rendiff-bucket
    credentials_file: /app/credentials/gcs.json

policies:
  # Allowed backends for input files
  input_backends:
    - local
    - s3
    - azure
    - gcs

  # Allowed backends for output files
  output_backends:
    - local
    - s3
    - azure
```

### Cloud Storage Environment Variables

**AWS S3:**

```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_DEFAULT_REGION=us-east-1
S3_BUCKET=my-bucket
```

**Azure Blob:**

```bash
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
AZURE_CONTAINER_NAME=rendiff-container
```

**Google Cloud:**

```bash
GOOGLE_APPLICATION_CREDENTIALS=/app/credentials/gcs.json
GCS_BUCKET=my-bucket
```

---

## Processing Configuration

### Worker Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKER_CONCURRENCY` | `4` | Concurrent jobs per worker |
| `MAX_CONCURRENT_JOBS` | `10` | Total concurrent jobs |
| `JOB_TIMEOUT` | `3600` | Maximum job duration (seconds) |
| `JOB_RETRY_MAX` | `3` | Maximum retry attempts |

**Example:**

```bash
WORKER_CONCURRENCY=4
MAX_CONCURRENT_JOBS=20
JOB_TIMEOUT=7200
```

### FFmpeg Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `FFMPEG_PATH` | `/usr/bin/ffmpeg` | FFmpeg binary path |
| `FFPROBE_PATH` | `/usr/bin/ffprobe` | FFprobe binary path |
| `FFMPEG_THREADS` | `0` | Threads (0=auto) |
| `FFMPEG_HARDWARE_ACCELERATION` | `auto` | Hardware acceleration |

**Hardware Acceleration Options:**

| Value | Description |
|-------|-------------|
| `auto` | Auto-detect available hardware |
| `none` | Disable hardware acceleration |
| `nvenc` | NVIDIA NVENC |
| `qsv` | Intel Quick Sync |
| `vaapi` | VA-API (Linux) |
| `videotoolbox` | macOS VideoToolbox |

**Example:**

```bash
FFMPEG_THREADS=0
FFMPEG_HARDWARE_ACCELERATION=nvenc
ENABLE_GPU_WORKERS=true
```

### Resource Limits

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_FILE_SIZE` | `10737418240` | Max upload size (10GB) |
| `MAX_RESOLUTION` | `7680x4320` | Max output resolution |
| `MAX_BITRATE` | `100M` | Max output bitrate |
| `MAX_OPERATIONS` | `50` | Max operations per job |

**Example:**

```bash
MAX_FILE_SIZE=21474836480   # 20GB
MAX_RESOLUTION=3840x2160    # 4K
MAX_BITRATE=50M
```

---

## Monitoring Configuration

### Prometheus Metrics

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_METRICS` | `true` | Enable /metrics endpoint |
| `METRICS_PORT` | `9090` | Prometheus port |

### Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Log level |
| `LOG_FORMAT` | `json` | Log format (json, text) |
| `LOG_FILE` | - | Log file path (optional) |

**Example:**

```bash
LOG_LEVEL=INFO
LOG_FORMAT=json
```

### Health Checks

| Variable | Default | Description |
|----------|---------|-------------|
| `HEALTH_CHECK_INTERVAL` | `30` | Check interval (seconds) |
| `HEALTH_CHECK_TIMEOUT` | `10` | Check timeout (seconds) |

---

## Docker Compose Configuration

### Environment File

The Docker Compose files read from `.env`:

```bash
# .env
COMPOSE_PROJECT_NAME=rendiff
POSTGRES_PASSWORD=secure_password
GRAFANA_PASSWORD=admin_password
```

### Volume Configuration

```bash
# Data persistence paths
POSTGRES_DATA_PATH=./data/postgres
REDIS_DATA_PATH=./data/redis
STORAGE_PATH=./storage
```

### Network Configuration

```bash
# Docker network
DOCKER_NETWORK=rendiff-network
```

---

## Production Configuration Example

Complete production `.env` file:

```bash
# =============================================================================
# RENDIFF PRODUCTION CONFIGURATION
# =============================================================================

# Application
DEBUG=false
API_LOG_LEVEL=info
API_WORKERS=8

# Database
DATABASE_URL=postgresql://rendiff_user:CHANGE_THIS_PASSWORD@postgres:5432/rendiff
DATABASE_POOL_SIZE=30
DATABASE_MAX_OVERFLOW=50

# Redis
REDIS_URL=redis://:REDIS_PASSWORD@redis:6379/0
REDIS_MAX_CONNECTIONS=200

# Security
ENABLE_API_KEYS=true
ADMIN_API_KEYS=sk-your-secure-admin-key
API_CORS_ORIGINS=https://app.yourdomain.com
RATE_LIMIT_CALLS=2000
RATE_LIMIT_PERIOD=3600

# Storage
STORAGE_PATH=/data/storage
TEMP_PATH=/tmp/rendiff

# Workers
WORKER_CONCURRENCY=4
MAX_CONCURRENT_JOBS=20
JOB_TIMEOUT=3600

# FFmpeg
FFMPEG_THREADS=0
FFMPEG_HARDWARE_ACCELERATION=auto

# Monitoring
ENABLE_METRICS=true
LOG_LEVEL=INFO
LOG_FORMAT=json

# Docker
COMPOSE_PROJECT_NAME=rendiff
POSTGRES_PASSWORD=CHANGE_THIS_PASSWORD
GRAFANA_PASSWORD=CHANGE_THIS_PASSWORD
```

---

## Configuration Validation

Rendiff validates configuration on startup. Check logs for warnings:

```bash
docker compose logs api | grep -i "config\|warn\|error"
```

Common validation warnings:

| Warning | Cause | Solution |
|---------|-------|----------|
| `DEBUG mode enabled` | DEBUG=true | Set DEBUG=false for production |
| `Default password detected` | Using default DB password | Change POSTGRES_PASSWORD |
| `CORS wildcard` | API_CORS_ORIGINS=* | Set specific origins |
| `API keys disabled` | ENABLE_API_KEYS=false | Enable for production |

---

## Environment-Specific Files

For different environments, create separate files:

```
.env.development
.env.staging
.env.production
```

Load with Docker Compose:

```bash
docker compose --env-file .env.production up -d
```
