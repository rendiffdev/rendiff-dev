# Setup Guide

Complete setup guide for Rendiff covering all deployment scenarios from development to production.

> **Powered by FFmpeg:** Rendiff is a REST API layer built on top of FFmpeg for media processing.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Setup Options](#setup-options)
3. [Development Setup](#development-setup)
4. [Production Setup](#production-setup)
5. [GPU Setup](#gpu-setup)
6. [HTTPS/SSL Configuration](#httpssl-configuration)
7. [Configuration Management](#configuration-management)
8. [Troubleshooting](#troubleshooting)

## Quick Start

**Single command setup for any deployment type:**

```bash
# Clone and navigate
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Choose your setup type
./setup.sh --help                    # Show all options
./setup.sh --development             # Quick dev setup
./setup.sh --standard                # Standard production
./setup.sh --gpu                    # Hardware accelerated production
```

## Setup Options

### 🚀 Quick Development
**Best for: Local development, testing, learning**

```bash
./setup.sh --development
```

**What you get:**
- SQLite database (no PostgreSQL needed)
- Local Redis
- Debug mode enabled
- No authentication required
- API available at http://localhost:8000

### 🏭 Standard Production
**Best for: CPU-based production deployment**

```bash
./setup.sh --standard
```

**What you get:**
- PostgreSQL database
- Redis queue system
- **HTTPS by default (self-signed certificate)**
- Traefik reverse proxy with SSL termination
- Prometheus monitoring
- API key authentication
- Production-optimized settings
- 2 CPU workers
- Automatic HTTP to HTTPS redirect

### ⚡ GPU Hardware Accelerated Production
**Best for: Hardware-accelerated video processing**

```bash
./setup.sh --gpu
```

**What you get:**
- Everything from Standard Production
- **HTTPS by default (self-signed certificate)**
- GPU support for hardware acceleration
- NVENC/NVDEC encoding support
- GPU workers for accelerated processing
- Enhanced performance capabilities
- Hardware acceleration endpoints at `/api/v1/gpu/*`

### 🛡️ Production with Let's Encrypt HTTPS
**Best for: Internet-facing deployments with domain names**

```bash
# Configure domain in .env file
DOMAIN_NAME=api.yourdomain.com
CERTBOT_EMAIL=admin@yourdomain.com

# Then run standard setup
./setup.sh --standard
```

**What you get:**
- Traefik reverse proxy with advanced SSL
- **Automatic SSL certificates (Let's Encrypt)**
- Certificate auto-renewal
- Enhanced security headers
- Rate limiting and DDoS protection
- SSL monitoring and alerts
- Access at https://your-domain.com

### ⚙️ Manual Configuration
**Best for: Custom configurations, advanced setups**

Edit the `.env` file directly for custom configurations:
- Storage backends (S3, Azure, GCP)
- SSL certificates  
- Advanced networking options
- Database settings

## Development Setup

Perfect for local development and testing:

### Prerequisites
- Docker Desktop
- 4GB+ RAM
- 10GB+ disk space

### Setup Process
```bash
# 1. Quick setup
./setup.sh --development

# 2. Verify deployment
curl http://localhost:8000/api/v1/health

# 3. Access documentation
open http://localhost:8000/docs
```

### Development Features
- **Hot reload** enabled for code changes
- **Debug logging** for troubleshooting
- **No authentication** for easy testing
- **SQLite database** (portable, no setup)
- **Simplified storage** (local filesystem)

### Development Commands
```bash
# View logs
docker compose logs -f api

# Restart API only
docker compose restart api

# Access database
docker compose exec api python -c "from api.database import engine; print(engine.url)"

# Run tests
docker compose exec api pytest

# Check status
./setup.sh --status
```

## Production Setup

Enterprise-ready deployment with full security and monitoring:

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 8GB+ RAM
- 50GB+ disk space
- Domain name (for HTTPS)

### Standard Production
```bash
# 1. Full setup
./setup.sh --standard

# 2. Validate deployment
./setup.sh --validate

# 3. Check all services
docker compose ps
```

### Production Features
- **PostgreSQL** database with optimizations
- **Redis** for queuing and caching
- **API key authentication** with rotation
- **Resource limits** and health checks
- **Prometheus metrics** collection
- **Grafana dashboards** for monitoring
- **Production logging** configuration

### Production with HTTPS
```bash
# 1. Configure domain
export DOMAIN_NAME=your-domain.com
export CERTBOT_EMAIL=admin@your-domain.com

# 2. Setup with HTTPS
./setup.sh --interactive
# Choose HTTPS option during setup

# 3. Verify SSL
curl -I https://your-domain.com/api/v1/health
```

### Production Commands
```bash
# Generate API keys
./scripts/manage-api-keys.sh generate

# Manage SSL certificates
./scripts/manage-ssl.sh list
./scripts/manage-ssl.sh renew

# Monitor services
./scripts/health-check.sh

# Backup data
./scripts/backup.sh create

# View production logs
docker compose logs -f

# Scale workers
docker compose up -d --scale worker-cpu=4
```

## GenAI Setup

AI-enhanced video processing with GPU acceleration:

### Prerequisites
- NVIDIA GPU with 8GB+ VRAM
- NVIDIA Docker runtime
- CUDA 11.8+ drivers
- 16GB+ system RAM
- 100GB+ disk space (for AI models)

### Setup Process
```bash
# 1. Verify GPU support
nvidia-smi

# 2. Setup GenAI environment
./setup.sh --genai

# 3. Wait for model downloads (may take 10-30 minutes)
docker compose logs -f model-downloader

# 4. Verify GenAI endpoints
curl https://localhost/api/genai/v1/health
```

### GenAI Features
- **Real-ESRGAN** upscaling (2x, 4x)
- **VideoMAE** scene analysis
- **VMAF** quality prediction
- **AI-powered** encoding optimization
- **Content analysis** (complexity, scenes)
- **Automated** bitrate ladders

### GenAI Commands
```bash
# Check GPU utilization
docker compose exec worker-genai nvidia-smi

# Download additional models
docker compose --profile setup run model-downloader

# Scale GenAI workers
docker compose up -d --scale worker-genai=2

# View GenAI logs
docker compose logs -f worker-genai
```

### AI Endpoints
```bash
# Scene detection
POST /api/genai/v1/analyze/scenes

# Video upscaling
POST /api/genai/v1/enhance/upscale

# Quality prediction
POST /api/genai/v1/predict/quality

# Encoding optimization
POST /api/genai/v1/optimize/parameters
```

## HTTPS/SSL Configuration

**🔒 Important:** ALL production deployments (`--standard`, `--genai`) come with HTTPS enabled by default using self-signed certificates. No additional configuration required!

### Default HTTPS Behavior

When you run production setup:
```bash
./setup.sh --standard
```

You automatically get:
- ✅ **HTTPS enabled on port 443**
- ✅ **HTTP to HTTPS redirect on port 80**
- ✅ **Self-signed certificate (valid for 365 days)**
- ✅ **Modern TLS 1.2/1.3 configuration**
- ✅ **Security headers enabled**
- ✅ **Certificate monitoring and expiration alerts**
- ✅ **Comprehensive SSL management tools**

### SSL Certificate Types Supported

#### 1. Self-Signed Certificates (Default)
- ✅ **Automatic generation**
- ✅ **Works immediately with localhost**
- ✅ **Perfect for development and internal use**
- ⚠️ **Browser security warnings (expected)**

#### 2. Let's Encrypt Certificates (Production)
- ✅ **Free, trusted certificates**
- ✅ **Automatic renewal**
- ✅ **No browser warnings**
- ✅ **Requires valid domain name**

#### 3. Commercial SSL Certificates
- ✅ **EV/OV certificate support**
- ✅ **Wildcard certificate support**
- ✅ **Custom CA integration**
- ✅ **Manual installation workflow**

### For Production Domains

#### Let's Encrypt Setup (Recommended)
```bash
# 1. Point your domain to the server
# 2. Configure domain in environment
export DOMAIN_NAME=api.example.com
export CERTBOT_EMAIL=admin@example.com

# 3. Setup with Let's Encrypt SSL
./setup.sh --interactive
# Choose option 2 for Standard + Let's Encrypt
# Choose option 4 for GenAI + Let's Encrypt
```

#### Commercial SSL Certificate Setup
```bash
# 1. Setup standard deployment first
./setup.sh --standard

# 2. Install your commercial certificate
./scripts/enhanced-ssl-manager.sh install-commercial /path/to/cert.crt /path/to/private.key

# 3. Restart services to apply certificate
docker compose restart traefik
```

### Manual SSL Management

#### Enhanced SSL Manager Commands
```bash
# Show all available commands
./scripts/enhanced-ssl-manager.sh --help

# Generate certificates
./scripts/enhanced-ssl-manager.sh generate-self-signed api.example.com
./scripts/enhanced-ssl-manager.sh generate-letsencrypt api.example.com admin@example.com

# Certificate information
./scripts/enhanced-ssl-manager.sh list                    # List all certificates
./scripts/enhanced-ssl-manager.sh show api.example.com   # Show certificate details
./scripts/enhanced-ssl-manager.sh check-expiration       # Check expiration dates

# Testing and validation
./scripts/enhanced-ssl-manager.sh test-ssl api.example.com
./scripts/enhanced-ssl-manager.sh validate /path/to/cert.crt

# Backup and restore
./scripts/enhanced-ssl-manager.sh backup                 # Backup all certificates
./scripts/enhanced-ssl-manager.sh restore 20240108       # Restore from backup

# Monitoring
./scripts/enhanced-ssl-manager.sh monitor-start          # Start SSL monitoring
./scripts/enhanced-ssl-manager.sh monitor-status         # Check monitor status
```

#### Legacy SSL Manager (Still Available)
```bash
# Generate Let's Encrypt certificate
./scripts/manage-ssl.sh generate-letsencrypt api.example.com admin@example.com

# Generate self-signed certificate (testing)
./scripts/manage-ssl.sh generate-self-signed api.example.com

# Test SSL configuration
./scripts/manage-ssl.sh test api.example.com

# Renew certificates
./scripts/manage-ssl.sh renew

# List certificates
./scripts/manage-ssl.sh list
```

### SSL Features

#### Security Features
- **Automatic renewal** of Let's Encrypt certificates
- **Security headers** (HSTS, CSP, X-Frame-Options, etc.)
- **TLS 1.2/1.3** support only (TLS 1.0/1.1 disabled)
- **Perfect forward secrecy** with ECDHE ciphers
- **OCSP stapling** for enhanced performance
- **HTTP/2 and HTTP/3** support

#### Monitoring & Management
- **Certificate expiration monitoring** with 30-day alerts
- **SSL connection testing** and validation
- **Certificate chain verification**
- **Automatic backup** of all certificates
- **Health checks** for SSL services
- **Performance monitoring** and metrics

#### Advanced Features
- **Multiple certificate types** (self-signed, Let's Encrypt, commercial)
- **Wildcard certificate** support
- **Multi-domain** certificate management
- **Certificate format conversion** (PEM, DER, PKCS#12)
- **CSR generation** for commercial certificates
- **Rate limiting** and DDoS protection

## Configuration Management

### Environment Variables
```bash
# View current configuration
cat .env

# Edit configuration
nano .env

# Reload configuration
docker compose restart api
```

### Key Configuration Files
- **`.env`** - Main environment configuration
- **`config/storage.yml`** - Storage backend configuration
- **`traefik/traefik.yml`** - Reverse proxy configuration
- **`monitoring/prometheus.yml`** - Metrics configuration

### API Key Management
```bash
# Generate new keys
./scripts/manage-api-keys.sh generate

# List current keys (masked)
./scripts/manage-api-keys.sh list

# Test key validity
./scripts/manage-api-keys.sh test

# Rotate all keys
./scripts/manage-api-keys.sh rotate

# Export keys for external use
./scripts/manage-api-keys.sh export
```

### Storage Configuration
```yaml
# config/storage.yml
storage:
  default_backend: "s3"  # or "local"
  backends:
    s3:
      type: "s3"
      bucket: "my-video-bucket"
      region: "us-east-1"
      access_key: "${AWS_ACCESS_KEY_ID}"
      secret_key: "${AWS_SECRET_ACCESS_KEY}"
```

## Troubleshooting

### Common Issues

#### 🚨 Services Won't Start
```bash
# Check Docker status
docker ps -a

# View error logs
docker compose logs api

# Validate configuration
./setup.sh --validate

# Check resource usage
docker stats
```

#### 🔑 Authentication Issues
```bash
# Verify API keys
./scripts/manage-api-keys.sh list

# Test API access
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/health

# Regenerate keys if needed
./scripts/manage-api-keys.sh generate
```

#### 🌐 Network Issues
```bash
# Check port conflicts
netstat -tulpn | grep :8000

# Verify Docker networks
docker network ls

# Test internal connectivity
docker compose exec api curl redis:6379
```

#### 💾 Database Issues
```bash
# Check database status
docker compose exec postgres pg_isready

# View database logs
docker compose logs postgres

# Run migrations manually
docker compose exec api alembic upgrade head

# Reset database (destructive)
docker compose down -v
./setup.sh --standard
```

#### 🤖 GenAI Issues
```bash
# Check GPU availability
nvidia-smi

# Verify CUDA in container
docker compose exec worker-genai nvidia-smi

# Check model downloads
ls -la models/genai/

# Restart GenAI services
docker compose restart worker-genai
```

### Performance Optimization

#### Resource Scaling
```bash
# Scale API instances
docker compose up -d --scale api=3

# Scale CPU workers
docker compose up -d --scale worker-cpu=4

# Scale GenAI workers (if GPU memory allows)
docker compose up -d --scale worker-genai=2
```

#### Database Optimization
```bash
# Monitor database performance
docker compose exec postgres psql -U rendiff_user -d rendiff -c "
SELECT query, mean_time, calls 
FROM pg_stat_statements 
ORDER BY mean_time DESC LIMIT 10;"

# Analyze table usage
docker compose exec postgres psql -U rendiff_user -d rendiff -c "
SELECT schemaname,tablename,attname,n_distinct,correlation 
FROM pg_stats WHERE tablename='jobs';"
```

### Getting Help

1. **Check logs**: `docker compose logs -f [service]`
2. **Validate setup**: `./setup.sh --validate`
3. **Health check**: `./scripts/health-check.sh`
4. **Documentation**: Browse `/docs` in this repository
5. **Issues**: Report at GitHub repository issues page

---

## 📚 Documentation Navigation

| Guide | Description | When to Use |
|-------|-------------|-------------|
| **[🏠 Main README](../README.md)** | Project overview and quick start | Start here |
| **[🚀 Setup Guide](SETUP.md)** | Complete deployment guide | **You are here** |
| **[🔧 API Reference](API.md)** | Detailed API documentation | Using the API |
| **[📦 Installation Guide](INSTALLATION.md)** | Advanced installation options | Custom installs |
| **[🏭 Production Setup](#production-setup)** | Production best practices | Production setup |
| **[🛡️ HTTPS/SSL Configuration](#httpssl-configuration)** | Security configuration | Security hardening |

**Need help?** Check the [troubleshooting section](#troubleshooting) or [open an issue](https://github.com/rendiffdev/rendiff-dev/issues).