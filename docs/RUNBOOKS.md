# Rendiff Operational Runbooks

## Table of Contents

1. [Service Health Checks](#service-health-checks)
2. [Common Issues and Resolution](#common-issues-and-resolution)
3. [Incident Response Procedures](#incident-response-procedures)
4. [Performance Troubleshooting](#performance-troubleshooting)
5. [Disaster Recovery](#disaster-recovery)
6. [Scaling Procedures](#scaling-procedures)
7. [Security Incidents](#security-incidents)

---

## Service Health Checks

### 🟢 Quick Health Check

```bash
# Check all services
curl -s https://api.domain.com/api/v1/health | jq .

# Check specific components
docker compose ps
docker compose exec api curl -s localhost:8000/api/v1/health
docker compose exec postgres pg_isready
docker compose exec redis redis-cli ping
```

### 🔍 Deep Health Check

```bash
# API response times
curl -w "@curl-format.txt" -o /dev/null -s https://api.domain.com/api/v1/health

# Database connections
docker compose exec postgres psql -U rendiff_user -d rendiff -c \
  "SELECT count(*) FROM pg_stat_activity WHERE datname = 'rendiff';"

# Queue depth
docker compose exec redis redis-cli llen celery

# Worker status
docker compose exec worker-cpu celery -A worker.main inspect active
```

---

## Common Issues and Resolution

### 🚨 Issue: High API Response Times

**Symptoms:**
- P95 latency > 5 seconds
- Timeouts on /convert endpoint
- User complaints about slow processing

**Diagnosis:**
```bash
# Check CPU usage
docker stats --no-stream

# Check database slow queries
docker compose exec postgres psql -U rendiff_user -d rendiff -c \
  "SELECT query, mean_exec_time, calls FROM pg_stat_statements 
   WHERE mean_exec_time > 1000 ORDER BY mean_exec_time DESC LIMIT 10;"

# Check Redis memory
docker compose exec redis redis-cli info memory
```

**Resolution:**
1. **Scale API containers:**
   ```bash
   docker compose up -d --scale api=4
   ```

2. **Clear slow queries:**
   ```bash
   # Analyze and optimize slow queries
   docker compose exec postgres psql -U rendiff_user -d rendiff -c \
     "ANALYZE jobs; REINDEX TABLE jobs;"
   ```

3. **Increase connection pool:**
   ```bash
   # Update DATABASE_POOL_SIZE in .env
   DATABASE_POOL_SIZE=40
   docker compose restart api
   ```

### 🚨 Issue: Jobs Stuck in Queue

**Symptoms:**
- Jobs remain in "queued" status
- Queue depth increasing
- No worker activity

**Diagnosis:**
```bash
# Check worker status
docker compose logs --tail=100 worker-cpu | grep ERROR

# Check queue status
docker compose exec redis redis-cli llen high
docker compose exec redis redis-cli llen default
docker compose exec redis redis-cli llen low

# Check worker processes
docker compose exec worker-cpu ps aux | grep celery
```

**Resolution:**
1. **Restart workers:**
   ```bash
   docker compose restart worker-cpu worker-gpu
   ```

2. **Scale workers:**
   ```bash
   docker compose up -d --scale worker-cpu=6
   ```

3. **Clear stuck jobs:**
   ```bash
   # Move stuck jobs back to queue
   docker compose exec api python -c "
   from api.models.job import Job, JobStatus
   from api.database import SessionLocal
   db = SessionLocal()
   stuck_jobs = db.query(Job).filter(
       Job.status == JobStatus.PROCESSING,
       Job.updated_at < datetime.now() - timedelta(hours=1)
   ).all()
   for job in stuck_jobs:
       job.status = JobStatus.QUEUED
   db.commit()
   "
   ```

### 🚨 Issue: Storage Full

**Symptoms:**
- "No space left on device" errors
- Jobs failing during output write
- Upload failures

**Diagnosis:**
```bash
# Check disk usage
df -h /storage

# Find large files
du -sh /storage/* | sort -hr | head -20

# Check for orphaned files
find /storage -type f -mtime +7 -name "*.tmp" -ls
```

**Resolution:**
1. **Clean temporary files:**
   ```bash
   # Remove old temporary files
   find /storage/tmp -type f -mtime +1 -delete
   
   # Clean orphaned job files
   docker compose exec api python scripts/cleanup-storage.py
   ```

2. **Archive old files to S3:**
   ```bash
   # Archive files older than 7 days
   aws s3 sync /storage/output/ s3://archive-bucket/output/ \
     --exclude "*" --include "*.mp4" --include "*.webm" \
     --exclude "$(date +%Y%m)*"
   ```

3. **Expand storage:**
   ```bash
   # Resize volume (AWS)
   aws ec2 modify-volume --volume-id vol-xxx --size 500
   
   # Resize filesystem
   sudo resize2fs /dev/xvdf
   ```

---

## Incident Response Procedures

### 📋 Severity Levels

| Level | Response Time | Examples |
|-------|--------------|----------|
| SEV1 | 15 minutes | Complete outage, data loss |
| SEV2 | 30 minutes | Degraded performance, partial outage |
| SEV3 | 2 hours | Minor issues, single component failure |
| SEV4 | Next business day | Cosmetic issues, documentation |

### 🚨 SEV1: Complete Service Outage

**Initial Response (0-15 min):**

1. **Acknowledge incident:**
   ```bash
   # Send initial notification
   ./scripts/notify-incident.sh SEV1 "FFmpeg API Complete Outage"
   ```

2. **Quick diagnostics:**
   ```bash
   # Check all services
   docker compose ps
   
   # Check recent deployments
   git log --oneline -10
   
   # Check system resources
   free -m
   df -h
   ```

3. **Immediate mitigation:**
   ```bash
   # Restart all services
   docker compose down
   docker compose up -d
   
   # Enable maintenance mode
   docker compose exec api redis-cli set maintenance_mode true
   ```

**Investigation (15-30 min):**

1. **Collect logs:**
   ```bash
   # Aggregate recent logs
   mkdir -p /tmp/incident-$(date +%Y%m%d-%H%M%S)
   cd /tmp/incident-*
   
   docker compose logs --since 1h > docker-logs.txt
   journalctl --since "1 hour ago" > system-logs.txt
   ```

2. **Check metrics:**
   - Open Grafana dashboard
   - Look for anomalies in last 2 hours
   - Check error rates and latency

3. **Root cause analysis:**
   ```bash
   # Check for OOM kills
   dmesg | grep -i "killed process"
   
   # Check for disk issues
   grep -i "error\|fail" /var/log/syslog
   
   # Database issues
   docker compose exec postgres tail -100 /var/log/postgresql/postgresql.log
   ```

**Recovery (30-60 min):**

1. **Restore service:**
   ```bash
   # If configuration issue, rollback
   git checkout HEAD~1 -- compose.yml
   docker compose up -d
   
   # If database issue, restore from backup
   ./scripts/disaster-recovery.sh --mode latest
   ```

2. **Verify recovery:**
   ```bash
   # Run smoke tests
   ./scripts/smoke-test.sh
   
   # Check metrics
   curl -s http://localhost:9090/metrics | grep up
   ```

3. **Post-incident:**
   ```bash
   # Disable maintenance mode
   docker compose exec api redis-cli del maintenance_mode
   
   # Send recovery notification
   ./scripts/notify-incident.sh RESOLVED "FFmpeg API Service Restored"
   ```

### 📝 Incident Report Template

```markdown
# Incident Report: [INCIDENT-ID]

**Date:** [DATE]
**Severity:** [SEV1/2/3/4]
**Duration:** [START] - [END]
**Impact:** [# of users affected, % of requests failed]

## Summary
[Brief description of what happened]

## Timeline
- **[TIME]** - Initial detection
- **[TIME]** - Incident acknowledged
- **[TIME]** - Root cause identified
- **[TIME]** - Fix implemented
- **[TIME]** - Service restored

## Root Cause
[Detailed explanation of why this happened]

## Resolution
[What was done to fix the issue]

## Impact
- **Users affected:** [number]
- **Requests failed:** [number]
- **Data loss:** [yes/no]

## Lessons Learned
1. [What went well]
2. [What went poorly]
3. [What was lucky]

## Action Items
- [ ] [Preventive measure 1]
- [ ] [Preventive measure 2]
- [ ] [Process improvement]
```

---

## Performance Troubleshooting

### 🐌 Slow Video Processing

**Check processing metrics:**
```bash
# Average processing time by operation
docker compose exec postgres psql -U rendiff_user -d rendiff -c "
SELECT 
    operations->0->>'type' as operation,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds,
    COUNT(*) as job_count
FROM jobs 
WHERE status = 'completed' 
    AND completed_at > NOW() - INTERVAL '1 day'
GROUP BY operations->0->>'type'
ORDER BY avg_seconds DESC;"
```

**Optimize FFmpeg settings:**
```bash
# Check current FFmpeg threads
docker compose exec worker-cpu cat /proc/cpuinfo | grep processor | wc -l

# Update worker concurrency
WORKER_CONCURRENCY=2  # Reduce to give more CPU per job
docker compose restart worker-cpu
```

### 📊 Database Performance

**Check slow queries:**
```bash
# Enable query logging
docker compose exec postgres psql -U rendiff_user -d rendiff -c \
  "ALTER SYSTEM SET log_min_duration_statement = 1000;"

docker compose exec postgres psql -U rendiff_user -d rendiff -c \
  "SELECT pg_reload_conf();"

# View slow query log
docker compose exec postgres tail -f /var/log/postgresql/postgresql.log | grep duration
```

**Optimize database:**
```bash
# Update statistics
docker compose exec postgres vacuumdb -U rendiff_user -d rendiff -z

# Reindex tables
docker compose exec postgres reindexdb -U rendiff_user -d rendiff

# Check table sizes
docker compose exec postgres psql -U rendiff_user -d rendiff -c "
SELECT
    schemaname AS table_schema,
    tablename AS table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;"
```

---

## Disaster Recovery

### 🔥 Complete Database Recovery

1. **Stop application:**
   ```bash
   docker compose stop api worker-cpu worker-gpu
   ```

2. **List available backups:**
   ```bash
   ./scripts/disaster-recovery.sh --mode list
   ```

3. **Restore from backup:**
   ```bash
   # Restore latest
   ./scripts/disaster-recovery.sh --mode latest
   
   # Restore specific backup
   ./scripts/disaster-recovery.sh --mode specific \
     --timestamp 20250127_120000
   ```

4. **Verify restoration:**
   ```bash
   # Check data integrity
   docker compose exec postgres psql -U rendiff_user -d rendiff -c \
     "SELECT COUNT(*) FROM jobs;"
   
   # Run application tests
   docker compose run --rm api pytest tests/
   ```

5. **Resume service:**
   ```bash
   docker compose up -d api worker-cpu worker-gpu
   ```

### 💾 Point-in-Time Recovery

```bash
# Enable WAL archiving (preventive)
docker compose exec postgres psql -U postgres -c "
ALTER SYSTEM SET wal_level = replica;
ALTER SYSTEM SET archive_mode = on;
ALTER SYSTEM SET archive_command = 'aws s3 cp %p s3://backup-bucket/wal/%f';
"

# Perform PITR
pg_basebackup -h localhost -D /recovery -U postgres -Fp -Xs -P
```

---

## Scaling Procedures

### ⬆️ Vertical Scaling (Resize)

1. **Plan maintenance window:**
   ```bash
   # Enable maintenance mode
   docker compose exec api redis-cli set maintenance_mode true ex 3600
   ```

2. **Scale instance (AWS):**
   ```bash
   # Stop instance
   aws ec2 stop-instances --instance-ids i-xxxxx
   
   # Modify instance type
   aws ec2 modify-instance-attribute --instance-id i-xxxxx \
     --instance-type c5.4xlarge
   
   # Start instance
   aws ec2 start-instances --instance-ids i-xxxxx
   ```

3. **Verify and adjust:**
   ```bash
   # Update resource limits
   docker compose down
   # Edit compose.yml with new limits
   docker compose up -d
   ```

### ➡️ Horizontal Scaling

1. **Add worker nodes:**
   ```bash
   # Deploy to new node
   scp -r . newnode:/opt/rendiff/
   ssh newnode "cd /opt/rendiff && docker compose up -d worker-cpu"
   ```

2. **Scale services:**
   ```bash
   # API servers
   docker compose up -d --scale api=6
   
   # CPU workers
   docker compose up -d --scale worker-cpu=10
   
   # GPU workers (if available)
   docker compose up -d --scale worker-gpu=4
   ```

3. **Update load balancer:**
   ```bash
   # Add new backend to Traefik
   docker compose exec traefik traefik healthcheck
   ```

---

## Security Incidents

### 🔐 Suspected API Key Compromise

1. **Immediate response:**
   ```bash
   # Identify compromised key
   docker compose exec postgres psql -U rendiff_user -d rendiff -c "
   SELECT api_key_hash, last_used_at, request_count 
   FROM api_keys 
   WHERE last_used_at > NOW() - INTERVAL '1 hour'
   ORDER BY request_count DESC;"
   
   # Revoke key
   ./scripts/manage-api-keys.sh revoke <key-hash>
   ```

2. **Investigate:**
   ```bash
   # Check access logs
   docker compose logs api | grep <key-hash> > suspicious-activity.log
   
   # Check for data exfiltration
   docker compose exec postgres psql -U rendiff_user -d rendiff -c "
   SELECT COUNT(*), SUM(output_size) 
   FROM jobs 
   WHERE api_key = '<key-hash>' 
     AND created_at > NOW() - INTERVAL '24 hours';"
   ```

3. **Remediate:**
   ```bash
   # Rotate all keys for affected user
   ./scripts/manage-api-keys.sh rotate-user <user-id>
   
   # Enable additional monitoring
   docker compose exec api redis-cli set "monitor:api_key:<key-hash>" true
   ```

### 🛡️ DDoS Attack Response

1. **Enable rate limiting:**
   ```bash
   # Update Traefik rate limits
   docker compose exec traefik redis-cli set "ratelimit:global" 100
   
   # Enable DDoS protection mode
   docker compose exec api python -c "
   from api.config import settings
   settings.ENABLE_DDOS_PROTECTION = True
   "
   ```

2. **Block malicious IPs:**
   ```bash
   # Analyze access patterns
   docker compose logs traefik | awk '{print $1}' | sort | uniq -c | sort -rn | head -20
   
   # Block suspicious IPs
   iptables -A INPUT -s MALICIOUS_IP -j DROP
   ```

3. **Scale and cache:**
   ```bash
   # Enable aggressive caching
   docker compose exec redis redis-cli config set maxmemory 4gb
   
   # Scale API servers
   docker compose up -d --scale api=10
   ```

---

## Monitoring Commands Reference

```bash
# Service health
curl -s localhost:8000/api/v1/health | jq .

# Queue status
docker compose exec redis redis-cli info clients

# Active jobs
docker compose exec worker-cpu celery -A worker.main inspect active

# Database connections
docker compose exec postgres psql -c "SELECT count(*) FROM pg_stat_activity;"

# Memory usage
docker stats --no-stream --format "table {{.Container}}\t{{.MemUsage}}"

# Disk usage
df -h | grep -E "Filesystem|storage"

# Network connections
netstat -an | grep ESTABLISHED | wc -l

# Error logs
docker compose logs --since 10m | grep -i error

# Performance metrics
curl -s localhost:9090/metrics | grep -E "http_request_duration|ffmpeg_job_duration"
```

---

## Emergency Contacts

- **On-Call Engineer**: Use PagerDuty
- **Database Admin**: dba-team@company.com
- **Infrastructure**: infra-team@company.com
- **Security Team**: security@company.com
- **Management Escalation**: cto@company.com

## Useful Links

- [Grafana Dashboard](http://monitoring.internal:3000)
- [Prometheus](http://monitoring.internal:9090)
- [Traefik Dashboard](http://traefik.internal:8080)
- [API Documentation](https://api.domain.com/docs)
- [Status Page](https://status.domain.com)