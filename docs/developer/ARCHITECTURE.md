# Rendiff Architecture

This document describes the system architecture of Rendiff, including component design, data flow, and integration patterns.

## System Overview

Rendiff follows a distributed microservices architecture optimized for high-throughput media processing workloads.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                     │
│                    (Web Apps, Mobile Apps, CLI Tools)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRAEFIK (Reverse Proxy)                          │
│              • SSL Termination  • Rate Limiting  • Load Balancing        │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
            ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
            │   API #1    │ │   API #2    │ │   API #N    │
            │  (FastAPI)  │ │  (FastAPI)  │ │  (FastAPI)  │
            └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
                   │               │               │
                   └───────────────┼───────────────┘
                                   │
           ┌───────────────────────┼───────────────────────┐
           ▼                       ▼                       ▼
    ┌─────────────┐        ┌─────────────┐        ┌─────────────┐
    │ PostgreSQL  │        │    Redis    │        │   Storage   │
    │  (Primary   │        │  (Queue +   │        │  (Local/S3/ │
    │   Database) │        │   Cache)    │        │   Azure)    │
    └─────────────┘        └──────┬──────┘        └─────────────┘
                                  │
                   ┌──────────────┼──────────────┐
                   ▼              ▼              ▼
            ┌─────────────┐┌─────────────┐┌─────────────┐
            │  Worker #1  ││  Worker #2  ││  Worker #N  │
            │  (Celery +  ││  (Celery +  ││  (Celery +  │
            │   FFmpeg)   ││   FFmpeg)   ││   FFmpeg)   │
            └─────────────┘└─────────────┘└─────────────┘
```

## Core Components

### 1. API Layer (FastAPI)

The API layer handles all HTTP requests and serves as the system's entry point.

**Responsibilities:**
- Request validation and authentication
- Job creation and status queries
- Health checks and metrics exposure
- WebSocket connections for real-time updates

**Key Files:**
```
api/
├── main.py              # Application factory, middleware setup
├── config.py            # Pydantic settings management
├── dependencies.py      # Dependency injection (DB, Redis, Auth)
├── routers/
│   ├── convert.py       # /api/v1/convert endpoints
│   ├── jobs.py          # /api/v1/jobs endpoints
│   ├── health.py        # /api/v1/health endpoints
│   └── admin.py         # /api/v1/admin endpoints
├── models/
│   ├── job.py           # Job SQLAlchemy model
│   ├── api_key.py       # API key model
│   └── database.py      # Database connection setup
├── services/
│   ├── job_service.py   # Job business logic
│   └── storage.py       # Storage abstraction
└── middleware/
    └── security.py      # Security middleware stack
```

**Request Flow:**
```
Request → Traefik → Security Middleware → Rate Limiter →
Authentication → Validation → Router → Service → Database → Response
```

### 2. Worker Layer (Celery)

Workers process media jobs asynchronously using FFmpeg.

**Responsibilities:**
- Consume jobs from Redis queue
- Execute FFmpeg commands
- Report progress updates
- Handle retries and failures
- Send webhook notifications

**Key Files:**
```
worker/
├── tasks.py             # Celery task definitions
├── celery_app.py        # Celery configuration
├── processors/
│   ├── video.py         # Video processing logic
│   ├── audio.py         # Audio processing logic
│   ├── analysis.py      # Quality analysis (VMAF, PSNR)
│   └── streaming.py     # HLS/DASH generation
└── utils/
    ├── ffmpeg.py        # FFmpeg command builder
    └── progress.py      # Progress tracking
```

**Task Flow:**
```
Job Created → Redis Queue → Worker Claims → Download Input →
FFmpeg Process → Upload Output → Update Database → Webhook
```

### 3. Database Layer (PostgreSQL)

PostgreSQL stores all persistent application data.

**Tables:**
| Table | Purpose |
|-------|---------|
| `jobs` | Processing job records |
| `api_keys` | Authentication credentials |
| `job_logs` | Detailed job event logs |
| `system_metrics` | Performance metrics |
| `storage_usage` | Storage tracking |

**Key Design Decisions:**
- UUID primary keys for distributed generation
- JSONB columns for flexible metadata
- Partial indexes for active job queries
- GIN indexes for JSON search

### 4. Queue Layer (Redis)

Redis serves dual purposes: message broker and cache.

**Usage:**
- **Celery Broker:** Job queue management
- **Rate Limiting:** Request counting per API key
- **Distributed Locks:** Preventing duplicate processing
- **Cache:** Temporary data storage
- **Progress Tracking:** Real-time job status

**Key Patterns:**
```python
# Rate limiting key structure
rate_limit:{api_key}:{endpoint} → count

# Job progress key structure
job:progress:{job_id} → {stage, percent, eta}

# Distributed lock
lock:job:{job_id} → worker_id (with TTL)
```

### 5. Storage Layer

Abstraction layer supporting multiple storage backends.

**Supported Backends:**
| Backend | Use Case |
|---------|----------|
| Local | Development, single-node deployments |
| S3 | AWS production deployments |
| Azure Blob | Azure production deployments |
| GCS | Google Cloud deployments |
| MinIO | Self-hosted S3-compatible storage |

**Storage Flow:**
```
Input URL → Parse Backend → Download to Temp →
Process with FFmpeg → Upload to Output Backend → Cleanup Temp
```

## Data Flow

### Job Processing Flow

```
1. Client submits job via POST /api/v1/convert
   │
2. API validates request and creates job record
   │
3. Job enqueued to Redis (Celery task)
   │
4. Worker claims job from queue
   │
5. Worker downloads input file to temp storage
   │
6. FFmpeg processes the file (with progress updates)
   │
7. Worker uploads output file to destination
   │
8. Database updated with completion status
   │
9. Webhook sent to client (if configured)
```

### Authentication Flow

```
1. Request received with X-API-Key header
   │
2. API key extracted and validated
   │
3. Key hash compared (constant-time)
   │
4. Rate limits checked against Redis
   │
5. Permissions validated for endpoint
   │
6. Request processed or rejected
```

## Scalability Design

### Horizontal Scaling

| Component | Scaling Strategy |
|-----------|-----------------|
| API | Add instances behind load balancer |
| Workers | Add worker containers/pods |
| Redis | Redis Cluster or Sentinel |
| PostgreSQL | Read replicas, connection pooling |
| Storage | Cloud storage (infinite scale) |

### Resource Limits

```yaml
# Per-job limits
MAX_INPUT_SIZE: 10GB
MAX_RESOLUTION: 7680x4320 (8K)
MAX_BITRATE: 100Mbps
MAX_DURATION: 24 hours
MAX_OPERATIONS: 50 per job

# Per-worker limits
FFMPEG_THREADS: Auto (CPU count)
MEMORY_LIMIT: Configurable
TEMP_STORAGE: Cleaned per job
```

## Security Architecture

### Defense in Depth

```
Layer 1: Network
├── Traefik rate limiting
├── IP whitelisting (optional)
└── TLS 1.2+ encryption

Layer 2: Authentication
├── API key validation
├── Timing attack protection
└── Key rotation support

Layer 3: Input Validation
├── Path traversal prevention
├── Command injection blocking
├── File type validation
└── Size limits

Layer 4: Processing
├── Sandboxed FFmpeg execution
├── Resource limits
└── Timeout enforcement

Layer 5: Output
├── Error message sanitization
├── SSRF prevention (webhooks)
└── Audit logging
```

## Monitoring Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    API      │────▶│ Prometheus  │────▶│   Grafana   │
│  /metrics   │     │  (Scraper)  │     │ (Dashboard) │
└─────────────┘     └─────────────┘     └─────────────┘
       │
       ▼
┌─────────────┐
│  Alerting   │
│   Rules     │
└─────────────┘
```

**Key Metrics:**
- `rendiff_jobs_total` - Job count by status
- `rendiff_job_duration_seconds` - Processing time histogram
- `rendiff_api_requests_total` - API request count
- `rendiff_storage_bytes` - Storage usage
- `rendiff_worker_active` - Active worker count

## Configuration Management

### Environment-Based Configuration

```
Production:   .env.production
Staging:      .env.staging
Development:  .env.development
Testing:      .env.test
```

### Configuration Hierarchy

```
1. Environment variables (highest priority)
2. .env file
3. Default values in config.py (lowest priority)
```

## Deployment Patterns

### Single Node (Development)

```
docker compose up -d
```

### Production (Docker Compose)

```
docker compose -f compose.prod.yml up -d
```

### Kubernetes

```
kubectl apply -f k8s/
```

See the [deployment guide](../user-manual/DEPLOYMENT.md) for detailed instructions.
