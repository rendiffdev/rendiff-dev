# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with Rendiff.

## Quick Diagnostics

### Check System Health

```bash
# API health check
curl http://localhost:8000/api/v1/health

# Docker service status
docker compose ps

# View recent logs
docker compose logs --tail=100
```

### Expected Health Response

```json
{
  "status": "healthy",
  "checks": {
    "database": {"status": "healthy"},
    "redis": {"status": "healthy"},
    "ffmpeg": {"status": "healthy"}
  }
}
```

---

## Common Issues

### 1. API Not Responding

**Symptoms:**
- Connection refused on port 8000
- Timeout errors

**Diagnosis:**

```bash
# Check if container is running
docker compose ps api

# Check API logs
docker compose logs api --tail=50

# Check if port is listening
netstat -tlnp | grep 8000
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Container not started | `docker compose up -d api` |
| Port conflict | Change `API_PORT` in `.env` |
| Startup crash | Check logs for errors |
| Health check failing | Check database/Redis connectivity |

### 2. Database Connection Failed

**Symptoms:**
- Health check shows database unhealthy
- `connection refused` errors in logs

**Diagnosis:**

```bash
# Check PostgreSQL status
docker compose ps postgres

# Test database connection
docker compose exec postgres psql -U rendiff_user -d rendiff -c "SELECT 1"

# Check connection URL
echo $DATABASE_URL
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| PostgreSQL not running | `docker compose up -d postgres` |
| Wrong credentials | Verify `DATABASE_URL` in `.env` |
| Database not created | Run migrations: `alembic upgrade head` |
| Network issue | Check Docker network connectivity |

**Reset Database:**

```bash
docker compose down -v
docker compose up -d postgres
sleep 10
docker compose exec api alembic upgrade head
docker compose up -d
```

### 3. Redis Connection Failed

**Symptoms:**
- Jobs stuck in pending state
- Rate limiting not working
- `Connection refused` errors

**Diagnosis:**

```bash
# Check Redis status
docker compose ps redis

# Test Redis connection
docker compose exec redis redis-cli ping

# Check Redis URL
echo $REDIS_URL
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Redis not running | `docker compose up -d redis` |
| Wrong password | Check `REDIS_URL` password |
| Memory exhausted | Increase Redis memory or clear cache |
| Network issue | Verify Docker network |

### 4. Jobs Stuck in Pending

**Symptoms:**
- Jobs created but never start processing
- Progress stays at 0%

**Diagnosis:**

```bash
# Check worker status
docker compose ps worker

# Check worker logs
docker compose logs worker --tail=50

# Check Celery queue
docker compose exec redis redis-cli LLEN celery
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| No workers running | `docker compose up -d worker` |
| Worker crashed | Check logs, restart: `docker compose restart worker` |
| Queue overloaded | Scale workers: `docker compose up -d --scale worker=4` |
| Redis connection lost | Restart Redis and workers |

### 5. FFmpeg Processing Errors

**Symptoms:**
- Jobs fail with processing errors
- Specific codecs/formats not working

**Diagnosis:**

```bash
# Check FFmpeg version
docker compose exec api ffmpeg -version

# Check FFmpeg codecs
docker compose exec api ffmpeg -codecs | grep -E "(h264|h265|vp9|aac)"

# Test FFmpeg manually
docker compose exec worker ffmpeg -i /storage/input.mp4 -c:v libx264 /tmp/test.mp4
```

**Common FFmpeg Errors:**

| Error | Cause | Solution |
|-------|-------|----------|
| `Unknown encoder` | Codec not available | Check codec name, use supported codec |
| `Invalid data found` | Corrupt input file | Verify input file integrity |
| `No such file` | File not found | Check file path and permissions |
| `Permission denied` | File permission issue | Fix file permissions |
| `Out of memory` | Insufficient RAM | Reduce resolution or bitrate |

### 6. Authentication Errors

**Symptoms:**
- 401 Unauthorized responses
- API key not accepted

**Diagnosis:**

```bash
# Test with API key
curl -H "X-API-Key: your-key" http://localhost:8000/api/v1/jobs

# Check if API keys enabled
echo $ENABLE_API_KEYS

# List API keys (admin)
curl -H "X-API-Key: admin-key" http://localhost:8000/api/v1/admin/api-keys
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| API keys disabled | Set `ENABLE_API_KEYS=true` |
| Invalid key format | Regenerate API key |
| Key expired | Create new key |
| Wrong header | Use `X-API-Key` header |

### 7. Rate Limit Exceeded

**Symptoms:**
- 429 Too Many Requests
- `Rate limit exceeded` error

**Diagnosis:**

```bash
# Check rate limit headers
curl -I -H "X-API-Key: key" http://localhost:8000/api/v1/jobs

# Headers show:
# X-RateLimit-Limit: 100
# X-RateLimit-Remaining: 0
# X-RateLimit-Reset: 1642000000
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Too many requests | Wait for rate limit reset |
| Low limit configured | Increase `RATE_LIMIT_CALLS` |
| Need higher tier | Upgrade API key tier |

### 8. Storage Errors

**Symptoms:**
- File not found errors
- Upload/download failures
- Permission denied

**Diagnosis:**

```bash
# Check storage directory
ls -la /storage/

# Check file permissions
docker compose exec api ls -la /storage/

# Test write access
docker compose exec api touch /storage/test.txt
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Directory doesn't exist | Create: `mkdir -p storage` |
| Permission denied | Fix ownership: `chown -R 1000:1000 storage` |
| Wrong path | Verify `STORAGE_PATH` |
| Disk full | Free up disk space |

### 9. Webhook Failures

**Symptoms:**
- Webhooks not received
- Jobs complete but no notification

**Diagnosis:**

```bash
# Check webhook URL in job
curl http://localhost:8000/api/v1/jobs/JOB_ID

# Check worker logs for webhook errors
docker compose logs worker | grep -i webhook
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| Invalid URL | Verify webhook URL format |
| Network blocked | Check firewall, ensure URL reachable |
| SSRF protection | Don't use internal IPs (10.x, 192.168.x) |
| Server error | Check your webhook endpoint |

### 10. Out of Memory

**Symptoms:**
- Container killed (OOMKilled)
- Processing very slow
- System unresponsive

**Diagnosis:**

```bash
# Check container memory usage
docker stats

# Check OOM kills
docker inspect api | grep -i oom
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| High resolution video | Reduce `MAX_RESOLUTION` |
| Too many workers | Reduce `WORKER_CONCURRENCY` |
| Memory leak | Restart workers regularly |
| Insufficient RAM | Add more RAM or scale horizontally |

---

## Log Analysis

### Viewing Logs

```bash
# All services
docker compose logs

# Specific service
docker compose logs api
docker compose logs worker

# Follow logs
docker compose logs -f api

# Last N lines
docker compose logs --tail=100 api

# Filter by time
docker compose logs --since="1h" api
```

### Common Log Patterns

**Successful Job:**

```
INFO  Job created: 550e8400-e29b-41d4-a716-446655440000
INFO  Job started: 550e8400-e29b-41d4-a716-446655440000
INFO  Processing: 25% complete
INFO  Processing: 50% complete
INFO  Processing: 75% complete
INFO  Job completed: 550e8400-e29b-41d4-a716-446655440000
```

**Failed Job:**

```
INFO  Job created: 550e8400-e29b-41d4-a716-446655440000
INFO  Job started: 550e8400-e29b-41d4-a716-446655440000
ERROR Processing failed: Invalid input file
ERROR Job failed: 550e8400-e29b-41d4-a716-446655440000
```

---

## Performance Issues

### Slow Processing

**Diagnosis:**

```bash
# Check system resources
docker stats

# Check job metrics
curl http://localhost:8000/api/v1/admin/stats

# Check FFmpeg process
docker compose exec worker ps aux | grep ffmpeg
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| CPU bottleneck | Enable hardware acceleration |
| Disk I/O slow | Use SSD storage |
| Network slow | Use local storage for processing |
| Wrong preset | Use faster preset (e.g., `fast`) |

### Hardware Acceleration Not Working

**Diagnosis:**

```bash
# Check GPU availability
docker compose exec worker nvidia-smi

# Check FFmpeg NVENC support
docker compose exec worker ffmpeg -encoders | grep nvenc
```

**Solutions:**

| Cause | Solution |
|-------|----------|
| No GPU | Use CPU encoding |
| Driver missing | Install NVIDIA drivers |
| Docker GPU access | Use `--gpus all` in Docker |
| Wrong FFmpeg build | Use GPU-enabled image |

---

## Recovery Procedures

### Full System Reset

```bash
# Stop all services
docker compose down

# Remove all data (WARNING: destroys all data)
docker compose down -v

# Restart fresh
docker compose up -d

# Run migrations
docker compose exec api alembic upgrade head
```

### Recover Stuck Jobs

```bash
# Find stuck jobs
curl "http://localhost:8000/api/v1/jobs?status=processing"

# Cancel stuck jobs via API
curl -X DELETE http://localhost:8000/api/v1/jobs/JOB_ID

# Or reset via database
docker compose exec postgres psql -U rendiff_user -d rendiff \
  -c "UPDATE jobs SET status='failed', error_message='Manual reset' WHERE status='processing'"
```

### Clear Queue

```bash
# Clear Celery queue
docker compose exec redis redis-cli FLUSHDB

# Restart workers
docker compose restart worker
```

---

## Getting Help

### Collect Diagnostic Information

Before reporting an issue, collect:

```bash
# System info
docker version
docker compose version
uname -a

# Service status
docker compose ps

# Recent logs
docker compose logs --tail=200 > logs.txt

# Health check
curl http://localhost:8000/api/v1/health > health.json

# Configuration (remove secrets!)
cat .env | grep -v PASSWORD | grep -v KEY > config.txt
```

### Report an Issue

1. Search [existing issues](https://github.com/rendiffdev/rendiff-dev/issues)
2. Create a new issue with:
   - Description of the problem
   - Steps to reproduce
   - Expected vs actual behavior
   - Diagnostic information (above)
   - Relevant log excerpts

### Community Support

- **GitHub Issues:** Bug reports and feature requests
- **GitHub Discussions:** Questions and community help
