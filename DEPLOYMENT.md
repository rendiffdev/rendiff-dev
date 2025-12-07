# Production Deployment Guide

Complete guide for deploying Rendiff to production environments.

## 📊 Executive Summary

**Rendiff** is a **production-ready**, **fully containerized** media processing API **powered by FFmpeg**. It provides enterprise-grade video/audio processing capabilities with optional AI-enhanced features.

> **Powered by FFmpeg:** All media processing operations are handled by FFmpeg under the hood. Rendiff provides a clean REST API layer on top of FFmpeg's powerful capabilities.

### 🎯 Key Features

#### Core API (Always Available)
- ✅ RESTful video/audio processing with FFmpeg 6.1
- ✅ Multi-format support (MP4, AVI, MOV, MKV, WebM, etc.)
- ✅ Async job processing with real-time progress tracking
- ✅ Quality analysis (VMAF, PSNR, SSIM)
- ✅ Streaming format generation (HLS/DASH)
- ✅ Multi-storage backend support (Local, S3-compatible)
- ✅ Hardware acceleration support (GPU/CPU)
- ✅ API authentication and rate limiting
- ✅ Comprehensive monitoring (Prometheus + Grafana)

#### GenAI Features (Optional)
- ✅ Real-ESRGAN video upscaling (2x, 4x, 8x)
- ✅ PySceneDetect + VideoMAE scene analysis
- ✅ AI-powered encoding parameter optimization
- ✅ Content complexity analysis and classification
- ✅ GPU acceleration with automatic CPU fallback

---

## 🚀 Quick Start - Zero Configuration

### Standard Deployment (Recommended)
```bash
# Clone and deploy - no setup required!
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev
docker compose up -d

# That's it! The API is now running at http://localhost:8080
```

### AI-Enhanced Deployment (GPU Required)
```bash
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev
docker compose -f docker compose.yml -f docker compose.genai.yml up -d
```

### What Happens Automatically:
- ✅ **PostgreSQL 15** database auto-configured with optimized settings
- ✅ **Redis 7** queue auto-configured for video workloads
- ✅ **Database schema** auto-created via migrations
- ✅ **FFmpeg 6.1** installed with all codecs enabled
- ✅ **Storage directories** created and configured
- ✅ **Health checks** activated for all services
- ✅ **API** ready to accept requests

---

## 🏗️ Architecture Overview

### Production Components
```
├── FastAPI (REST API)           # High-performance async API
├── Celery Workers               # Distributed task processing
├── PostgreSQL 15                # Primary database (auto-configured)
├── Redis 7                      # Job queue & caching (auto-configured)
├── FFmpeg 6.1                   # Video processing engine
├── Storage Backends             # Local + S3-compatible storage
├── Prometheus + Grafana         # Monitoring and metrics
└── Docker Containers            # Fully containerized deployment
```

### Container Structure
```
docker/
├── api/
│   ├── Dockerfile              # Standard API container
│   └── Dockerfile.genai        # GPU-enabled API container
├── worker/
│   ├── Dockerfile              # Standard worker container  
│   └── Dockerfile.genai        # GPU-enabled worker container
├── postgres/init/
│   ├── 01-init-db.sql         # Database initialization
│   └── 02-create-schema.sql   # Schema creation
├── redis/
│   └── redis.conf             # Production Redis config
└── install-ffmpeg.sh          # FFmpeg installation script
```

---

## 📋 Pre-Deployment Configuration

### 1. Environment Setup
```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration:
RENDIFF_API_KEY=your-secure-32-char-api-key
DATABASE_URL=postgresql+asyncpg://rendiff:rendiff@postgres:5432/rendiff
REDIS_URL=redis://redis:6379/0

# Optional: Enable GenAI features
GENAI_ENABLED=false  # Set to true for AI features
GENAI_GPU_ENABLED=false  # Set to true if GPU available
```

### 2. Storage Configuration
```bash
# Copy storage template
cp config/storage.yml.example config/storage.yml

# Configure your storage backends (S3 example):
# Edit config/storage.yml with your S3 credentials
```

### 3. API Key Generation
```bash
# Generate a secure API key
openssl rand -hex 32
```

---

## 🐳 Deployment Options

### Option 1: Development/Testing Setup
```bash
# Uses SQLite + local storage - perfect for testing
docker compose -f docker compose.setup.yml up -d
```

### Option 2: Production Deployment
```bash
# Full production stack with PostgreSQL and monitoring
docker compose --profile postgres --profile monitoring up -d
```

### Option 3: Production with AI Features
```bash
# Requires NVIDIA GPU with CUDA support
docker compose -f docker compose.yml -f docker compose.genai.yml up -d
```

### Option 4: Auto-Setup with Cloud Storage
```bash
# Environment-based auto-configuration
RENDIFF_AUTO_SETUP=true \
AWS_ACCESS_KEY_ID=your_key \
AWS_SECRET_ACCESS_KEY=your_secret \
AWS_S3_BUCKET=your-bucket \
docker compose up -d
```

---

## ✅ Production Readiness Checklist

### Core Functionality
- [x] Video transcoding with hardware acceleration
- [x] Quality analysis (VMAF, PSNR, SSIM)
- [x] Streaming format generation (HLS/DASH)
- [x] Real-time progress tracking
- [x] Multi-storage backend support

### Production Features
- [x] API authentication and authorization
- [x] Comprehensive error handling
- [x] Resource monitoring and limits
- [x] Health checks and metrics
- [x] Docker containerization

### Scalability
- [x] Horizontal worker scaling
- [x] Load balancer ready
- [x] Queue-based job processing
- [x] Storage backend abstraction
- [x] Monitoring and alerting

### Security
- [x] Input validation and sanitization
- [x] API key authentication
- [x] Resource limits and timeouts
- [x] Non-root container execution
- [x] Network isolation between services

### Reliability
- [x] Graceful error handling
- [x] Job retry mechanisms
- [x] Database migrations
- [x] Auto-recovery features
- [x] Comprehensive logging

---

## 🧪 Deployment Validation

### 1. Health Check
```bash
# Basic health check
curl http://localhost:8080/api/v1/health

# Detailed health check
curl http://localhost:8080/api/v1/health/detailed

# Expected response:
# {"status": "healthy", "version": "1.0.0", "services": {...}}
```

### 2. Test Video Processing
```bash
# Submit a test conversion job
curl -X POST http://localhost:8080/api/v1/convert \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "input_path": "test.mp4",
    "output_path": "output.mp4",
    "operations": [
      {
        "type": "transcode",
        "params": {
          "video_codec": "h264",
          "audio_codec": "aac",
          "video_bitrate": "2M"
        }
      }
    ]
  }'

# Check job status
curl http://localhost:8080/api/v1/jobs/{job_id} \
  -H "X-API-Key: your-api-key"
```

### 3. Test Quality Analysis
```bash
curl -X POST http://localhost:8080/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "reference_path": "original.mp4",
    "test_path": "encoded.mp4"
  }'
```

### 4. Test AI Features (if enabled)
```bash
# AI scene analysis
curl -X POST http://localhost:8080/api/genai/v1/analyze/scenes \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"video_path": "test.mp4"}'

# Video upscaling
curl -X POST http://localhost:8080/api/genai/v1/enhance/upscale \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{"video_path": "test.mp4", "scale": 2}'
```

### 5. System Verification
```bash
# Check capabilities
curl http://localhost:8080/api/v1/capabilities

# Monitor workers
curl http://localhost:8080/api/v1/workers

# Check storage backends
curl http://localhost:8080/api/v1/storage
```

---

## 🔧 Performance Optimization

### 1. Hardware Acceleration
```bash
# For GPU acceleration
docker compose --profile gpu up -d

# Verify GPU availability
curl http://localhost:8080/api/v1/capabilities
```

### 2. Worker Scaling
```bash
# Scale CPU workers
docker compose up -d --scale worker-cpu=6

# Scale GPU workers (if available)
docker compose up -d --scale worker-gpu=2

# Monitor worker utilization
curl http://localhost:8080/api/v1/workers
```

### 3. Resource Limits
```yaml
# Configure in docker compose.yml
deploy:
  resources:
    limits:
      memory: 4G
      cpus: '4.0'
    reservations:
      memory: 2G
      cpus: '2.0'
```

---

## 📊 Monitoring & Operations

### 1. Access Monitoring Dashboards
```bash
# Prometheus metrics
http://localhost:9090

# Grafana dashboards (default: admin/admin)
http://localhost:3000
```

### 2. View Logs
```bash
# API logs
docker compose logs -f api

# Worker logs
docker compose logs -f worker-cpu

# All services
docker compose logs -f
```

### 3. Performance Metrics
```bash
# Real-time stats
curl http://localhost:8080/api/v1/stats?period=1h

# Worker metrics
curl http://localhost:8080/api/v1/metrics
```

---

## 🚨 Troubleshooting Guide

### Services Won't Start
```bash
# Check service status
docker compose ps

# View detailed logs
docker compose logs api
docker compose logs postgres
docker compose logs redis

# Verify port availability
netstat -tlnp | grep -E "(8080|5432|6379)"
```

### Database Connection Issues
```bash
# Check PostgreSQL status
docker compose exec postgres pg_isready

# Verify database creation
docker compose exec postgres psql -U rendiff -d rendiff -c "\dt"

# Reset database (WARNING: data loss)
docker compose down -v
docker compose up -d
```

### Storage Connection Errors
```bash
# Test storage access
curl http://localhost:8080/api/v1/storage/test

# Check permissions
docker compose exec api ls -la /app/storage
```

### FFmpeg Processing Failures
```bash
# Verify FFmpeg installation
docker compose exec api ffmpeg -version

# Check available codecs
docker compose exec api ffmpeg -encoders
```

### Performance Issues
```bash
# Monitor resource usage
docker stats

# Check worker distribution
curl http://localhost:8080/api/v1/workers

# Scale workers if needed
docker compose up -d --scale worker-cpu=8
```

---

## 🔒 Security Best Practices

### 1. API Security
```bash
# Always use strong API keys
openssl rand -hex 32

# Configure rate limiting in .env
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60
```

### 2. Network Security
```bash
# Use reverse proxy with SSL
# Example nginx configuration available in docs/nginx-ssl.conf

# Restrict API access
# Configure firewall rules for production
```

### 3. Container Security
- All containers run as non-root users
- Resource limits enforced
- Network isolation between services
- Regular security updates recommended

---

## 📊 Performance Specifications

### Standard API Performance
- **Throughput**: 10-50 concurrent jobs (hardware dependent)
- **API Latency**: <2s response time
- **Processing Speed**: ~0.5-2x realtime
- **Storage**: Local filesystem or S3-compatible
- **Scaling**: Horizontal worker scaling supported

### AI-Enhanced Performance
- **Processing Improvement**: 2-5x encoding efficiency
- **Quality Gain**: 10-15% better compression
- **Upscaling**: 2-4x resolution enhancement
- **GPU Memory**: 8-24GB VRAM recommended
- **CPU Fallback**: Available but 5-10x slower

---

## 🎉 Post-Deployment Steps

### 1. Production Verification
- ✅ Confirm all health checks pass
- ✅ Process test videos successfully
- ✅ Verify monitoring dashboards work
- ✅ Test API authentication
- ✅ Check log aggregation

### 2. Performance Tuning
- Monitor processing times and optimize worker counts
- Adjust resource limits based on actual usage
- Configure storage for optimal performance
- Set up alerting for critical metrics

### 3. Scaling Strategy
- Plan horizontal scaling based on load patterns
- Consider multi-region deployments
- Implement auto-scaling policies
- Set up load balancing

---

## 📚 Additional Resources

- **API Documentation**: http://localhost:8080/docs
- **OpenAPI Spec**: http://localhost:8080/openapi.json
- **Grafana Dashboards**: http://localhost:3000
- **Prometheus Metrics**: http://localhost:9090
- **Support**: dev@rendiff.dev

---

**🎬 Your Rendiff FFmpeg API is now ready for production video processing! 🎉**

For additional support or enterprise features, contact the Rendiff team at dev@rendiff.dev.