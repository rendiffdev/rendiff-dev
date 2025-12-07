# Rendiff

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-%230db7ed.svg?logo=docker&logoColor=white)](https://www.docker.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-005571?logo=fastapi)](https://fastapi.tiangolo.com/)
[![Powered by FFmpeg](https://img.shields.io/badge/Powered%20by-FFmpeg-green?logo=ffmpeg)](https://ffmpeg.org/)
[![Production Ready](https://img.shields.io/badge/Production-Ready-brightgreen)](https://github.com/rendiffdev/rendiff-dev)
[![Security Hardened](https://img.shields.io/badge/Security-Hardened-red)](https://github.com/rendiffdev/rendiff-dev/blob/main/SECURITY.md)

**Rendiff** is an enterprise-grade REST API layer built on top of [FFmpeg](https://ffmpeg.org/), the industry-standard multimedia framework. Replace complex FFmpeg CLI operations with a modern, secure, and scalable REST API featuring hardware acceleration, real-time progress tracking, and comprehensive security hardening.

> **Powered by FFmpeg:** This project leverages FFmpeg for all media processing operations. FFmpeg is a complete, cross-platform solution to record, convert, and stream audio and video. Learn more at [ffmpeg.org](https://ffmpeg.org/).

> **🔒 Security Note:** This API has undergone comprehensive security hardening with all 34 critical vulnerabilities resolved. Safe for production deployment.

## About Rendiff

Rendiff provides a production-ready API abstraction over FFmpeg, making it easy to integrate powerful media processing capabilities into your applications without dealing with FFmpeg's complex CLI interface directly.

**What Rendiff Does:**
- Exposes FFmpeg's capabilities through a clean REST API
- Handles job queuing, progress tracking, and error handling
- Provides enterprise security features (auth, rate limiting, input validation)
- Supports distributed processing with multiple workers
- Integrates with cloud storage (S3, Azure, GCP)

**What FFmpeg Does (Under the Hood):**
- All actual media encoding, decoding, and transcoding
- Hardware acceleration (NVENC, QSV, VAAPI)
- Format conversion and streaming generation
- Quality analysis (VMAF, PSNR, SSIM)

## ✨ Key Features

### **Core Processing (Powered by FFmpeg)**
- **Complete FFmpeg Capability** - Full CLI parity with REST API convenience
- **Hardware Acceleration** - NVENC, QSV, VAAPI, VideoToolbox support
- **Quality Metrics** - Built-in VMAF, PSNR, SSIM analysis via FFmpeg
- **Async Processing** - Non-blocking operations with real-time progress
- **Batch Operations** - Process multiple files concurrently
- **Streaming Support** - Generate HLS/DASH adaptive streams

### **Enterprise Security** 🔒
- **Multi-layered Authentication** - API keys with role-based access
- **Rate Limiting** - Endpoint-specific limits with burst control
- **Input Validation** - Comprehensive sanitization and size limits
- **Path Traversal Protection** - Advanced canonicalization security
- **Command Injection Prevention** - Secure FFmpeg parameter handling
- **SSRF Protection** - Webhook URL validation and internal network blocking
- **Timing Attack Mitigation** - Constant-time API key validation

### **Production Reliability** 🚀
- **Circuit Breaker Pattern** - Automatic failure protection for external services
- **Distributed Locking** - Redis-based coordination for critical sections
- **Health Monitoring** - Comprehensive dependency health checks
- **Connection Pooling** - Optimized database and storage connections
- **Resource Limits** - CPU, memory, and bandwidth governance
- **Webhook Retry Logic** - Exponential backoff with failure handling
- **Performance Monitoring** - Prometheus metrics with Grafana dashboards

### **Storage & Infrastructure**
- **Multi-Cloud Storage** - S3, Azure, GCP, and local filesystem
- **Atomic Operations** - TOCTOU-safe file handling
- **Memory Management** - Guaranteed cleanup and leak prevention
- **Database Optimization** - Indexed queries and transaction isolation
- **Container Native** - Production-optimized Docker deployment

## 🚀 Quick Start

```bash
# Clone and deploy
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Run database migration for performance indexes
docker compose run --rm api alembic upgrade head

# Deploy all services
docker compose -f compose.prod.yml up -d

# API is now available at http://localhost:8000
curl http://localhost:8000/api/v1/health
```

> **🔧 Migration Note:** Run `alembic upgrade head` before deployment to add performance indexes.

For detailed setup options, see the [Setup Guide](docs/SETUP.md).

## 📋 API Endpoints

### Core Processing
```http
POST   /api/v1/convert     # Media conversion (FFmpeg transcode)
POST   /api/v1/analyze     # Quality metrics (VMAF, PSNR, SSIM)
POST   /api/v1/stream      # HLS/DASH adaptive streaming
POST   /api/v1/batch       # Batch processing
```

### Job Management
```http
GET    /api/v1/jobs        # List jobs
GET    /api/v1/jobs/{id}   # Job status
DELETE /api/v1/jobs/{id}   # Cancel job
```

### System & Monitoring
```http
GET    /api/v1/health      # Comprehensive health check
GET    /api/v1/metrics     # Prometheus metrics
GET    /api/v1/stats       # System statistics
GET    /docs               # Interactive API documentation
```

## 🏗️ Architecture

```yaml
Rendiff Services:
├── API (FastAPI)           # REST API with security hardening
├── Workers (Celery)        # FFmpeg processing with circuit breakers
├── Queue (Redis/Valkey)    # Task queue with distributed locking
├── Database (PostgreSQL)   # ACID transactions with performance indexes
├── Storage (Multi-cloud)   # S3/Azure/GCP with connection pooling
├── Monitoring              # Prometheus/Grafana with comprehensive health checks
└── Security                # Rate limiting, input validation, SSRF protection

FFmpeg Integration:
└── Workers execute FFmpeg commands for all media operations
    ├── Transcoding (H.264, H.265, VP9, AV1)
    ├── Hardware acceleration (NVENC, QSV, VAAPI)
    ├── Streaming (HLS, DASH)
    └── Quality analysis (VMAF, PSNR, SSIM)
```

### **Security Layers**
```yaml
Defense in Depth:
├── Network: Rate limiting, IP whitelisting
├── Authentication: API keys with timing attack protection
├── Input: Size limits, path traversal prevention, sanitization
├── Processing: Command injection prevention, resource limits
├── Output: Information disclosure prevention, webhook validation
└── Infrastructure: Circuit breakers, distributed locking, health monitoring
```

## 📊 Format Support

**Input:** MP4, AVI, MOV, MKV, WebM, FLV, MP3, WAV, FLAC, AAC, and more
**Output:** MP4, WebM, MKV, HLS, DASH with H.264, H.265, VP9, AV1 codecs

> All format support is provided by FFmpeg. See [FFmpeg Formats Documentation](https://ffmpeg.org/ffmpeg-formats.html) for complete list.

## 🔧 Configuration

Configuration via environment variables or `.env` file:

```bash
# Core Services
API_HOST=0.0.0.0
API_PORT=8000
DATABASE_URL=postgresql://user:pass@localhost/rendiff
VALKEY_URL=redis://localhost:6379

# Security (Production Hardened)
ENABLE_API_KEYS=true
ENABLE_IP_WHITELIST=false
RATE_LIMIT_CALLS=2000
RATE_LIMIT_PERIOD=3600
MAX_FILE_SIZE=10737418240  # 10GB
MAX_CONCURRENT_JOBS=10

# Performance & Reliability
WORKER_CONCURRENCY=4
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=40
CIRCUIT_BREAKER_ENABLED=true
HEALTH_CHECK_INTERVAL=30

# FFmpeg / Hardware Acceleration
FFMPEG_HARDWARE_ACCELERATION=auto
ENABLE_GPU_WORKERS=false
FFMPEG_THREADS=0  # 0 = auto-detect
FFMPEG_PRESET=medium
```

### **Security Configuration**
```bash
# Authentication
API_KEY_LENGTH=32
API_KEY_EXPIRY_DAYS=365
ENABLE_ADMIN_ENDPOINTS=false

# Rate Limiting (per API key)
ANALYZE_RATE_LIMIT=100/hour
STREAM_RATE_LIMIT=50/hour
CONVERT_RATE_LIMIT=200/hour

# Resource Limits
MAX_RESOLUTION=7680x4320  # 8K
MAX_BITRATE=100M
MAX_PROCESSING_TIME=3600  # 1 hour
```

## 📚 Documentation

### **Setup & Deployment**
- [Setup Guide](docs/SETUP.md) - Installation and configuration
- [Deployment Guide](DEPLOYMENT.md) - Production deployment with security hardening
- [Migration Guide](docs/MIGRATION.md) - Database migrations and upgrades
- [Security Guide](SECURITY.md) - Security policies and hardening checklist

### **API & Development**
- [API Reference](docs/API.md) - Complete endpoint documentation with examples
- [Authentication Guide](docs/AUTH.md) - API key management and security
- [Webhook Guide](docs/WEBHOOKS.md) - Webhook configuration and retry logic
- [Contributing](CONTRIBUTING.md) - Development guidelines and standards

### **Operations & Monitoring**
- [Health Monitoring](docs/HEALTH.md) - Health checks and dependency monitoring
- [Performance Tuning](docs/PERFORMANCE.md) - Optimization and scaling guidelines
- [Runbooks](docs/RUNBOOKS.md) - Operational procedures and troubleshooting
- [Audit Report](CRITICAL_ISSUES_AUDIT.md) - Security vulnerability assessment (resolved)

## 🚦 System Requirements

### **Minimum (Development)**
- CPU: 4 cores
- RAM: 8GB
- Storage: 50GB SSD
- Network: 100 Mbps

### **Recommended (Production)**
- CPU: 8+ cores (16+ for high throughput)
- RAM: 32GB (64GB+ for 4K/8K processing)
- GPU: NVIDIA RTX/Quadro or AMD for hardware acceleration
- Storage: 500GB+ NVMe SSD (1TB+ for high volume)
- Network: 1 Gbps+ (10 Gbps for streaming workloads)

### **Enterprise (High Availability)**
- CPU: 16+ cores per node, multi-node cluster
- RAM: 64GB+ per node
- GPU: Multiple NVIDIA A100/H100 or equivalent
- Storage: High-performance SAN with 10K+ IOPS
- Network: 25 Gbps+ with redundancy
- Load Balancer: HAProxy/NGINX for multi-instance deployment

### **Dependencies**
- **Container Runtime**: Docker 20.10+ or containerd
- **FFmpeg**: 6.0+ (included in Docker images)
- **Database**: PostgreSQL 14+ (recommended) or SQLite 3.38+
- **Cache/Queue**: Redis 7.0+ or Valkey
- **Monitoring**: Prometheus + Grafana (optional)
- **Reverse Proxy**: Traefik, NGINX, or HAProxy (production)

## 🔒 Security & Compliance

Rendiff has undergone comprehensive security hardening:

### **Security Audit Status** ✅
- **34/34 Critical Issues Resolved** - All vulnerabilities patched
- **Zero Known CVEs** - Dependencies updated to secure versions
- **Production Ready** - Approved for enterprise deployment
- **Penetration Tested** - Hardened against common attack vectors

### **Compliance Features**
- **Input Validation** - All user inputs sanitized and validated
- **Rate Limiting** - DDoS protection with endpoint-specific limits
- **Access Control** - Role-based API key authentication
- **Audit Logging** - Comprehensive security event logging
- **Encryption** - TLS 1.3 for data in transit
- **Secrets Management** - Environment-based configuration

### **Security Reports**
- [Security Audit Report](CRITICAL_ISSUES_AUDIT.md) - Comprehensive vulnerability assessment
- [Fixes Implementation Report](FIXES_COMPLETED_REPORT.md) - Resolution documentation
- [Security Policy](SECURITY.md) - Security guidelines and procedures

## 🙏 Acknowledgments

### FFmpeg

**Rendiff is powered by [FFmpeg](https://ffmpeg.org/)**, the leading multimedia framework.

> FFmpeg is a trademark of Fabrice Bellard, originator of the FFmpeg project.

FFmpeg is licensed under the [LGPL/GPL license](https://ffmpeg.org/legal.html). This project uses FFmpeg as an external tool and does not modify or redistribute FFmpeg source code.

**FFmpeg provides:**
- Audio and video encoding/decoding
- Format conversion and muxing
- Hardware acceleration support
- Streaming protocols
- Quality analysis tools

We are grateful to the FFmpeg team and contributors for their incredible work on this essential multimedia toolkit.

### Other Technologies
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Celery](https://docs.celeryq.dev/) - Distributed task queue
- [PostgreSQL](https://postgresql.org/) - Advanced open source database
- [Redis](https://redis.io/) - In-memory data structure store

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### **Development Workflow**
```bash
# Set up development environment
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v

# Run security checks
bandit -r api/ worker/
safety check
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

**Note:** While Rendiff is MIT licensed, it depends on FFmpeg which is licensed under LGPL/GPL. When deploying, ensure compliance with FFmpeg's licensing terms. See [FFmpeg Legal](https://ffmpeg.org/legal.html) for details.

---

## 🏆 Production Ready

**Enterprise-grade media processing API powered by FFmpeg.**

- ✅ **34 Critical Security Issues Resolved**
- ✅ **Zero Breaking Changes** - Fully backward compatible
- ✅ **Production Tested** - Battle-tested architecture
- ✅ **Performance Optimized** - Database indexes, connection pooling, async I/O
- ✅ **Monitoring Ready** - Health checks, metrics, alerting
- ✅ **Scalable Design** - Horizontal scaling with load balancing

*Built with FastAPI, FFmpeg 6.0+, Redis, PostgreSQL, and Docker for professional video processing workflows.*

**Ready for immediate production deployment.** 🚀
