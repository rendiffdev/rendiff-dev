# Security Configuration Guide

## Overview

This guide provides comprehensive security configuration instructions for Rendiff to ensure production-grade security.

> **Note:** Rendiff is a REST API layer powered by FFmpeg. All media processing is handled by FFmpeg under the hood.

## 1. Environment Variables

### Required Security Environment Variables

Create a `.env` file based on `.env.example` and configure the following:

```bash
# Database - Use strong passwords
POSTGRES_PASSWORD=<generate-strong-password>

# Admin Access - Generate secure admin keys
ADMIN_API_KEYS=<key1>,<key2>

# Monitoring
GRAFANA_PASSWORD=<secure-grafana-password>
```

### Generating Secure Passwords and API Keys

```bash
# Generate secure passwords
openssl rand -base64 32

# Generate API keys using the provided script
./scripts/generate-api-key.py --admin -n 2
```

## 2. API Security

### API Key Management

1. **Enable API Key Authentication** (enabled by default)
   ```bash
   ENABLE_API_KEYS=true
   ```

2. **Configure Admin API Keys**
   ```bash
   # Generate secure admin keys
   ./scripts/generate-api-key.py --admin -n 2
   
   # Add to .env file
   ADMIN_API_KEYS=<generated-keys>
   ```

3. **API Key Usage**
   ```bash
   # Include in request headers
   curl -H "X-API-Key: your-api-key" https://api.example.com/v1/jobs
   ```

### IP Whitelisting

Enable IP whitelisting for additional security:

```bash
ENABLE_IP_WHITELIST=true
IP_WHITELIST=10.0.0.0/8,192.168.0.0/16,your.public.ip/32
```

## 3. Network Security

### TLS/SSL Configuration

1. **Use HTTPS in Production**
   - Configure reverse proxy (nginx/traefik) with SSL certificates
   - Redirect all HTTP traffic to HTTPS

2. **Internal Service Communication**
   - Keep internal services on a private network
   - Use Docker networks for isolation

### CORS Configuration

Configure allowed origins restrictively:

```bash
# In .env file
CORS_ORIGINS=https://app.example.com,https://admin.example.com
```

## 4. Container Security

### Docker Security Best Practices

1. **Run as Non-Root User**
   - All containers run as non-root users by default

2. **Read-Only Root Filesystem**
   - API containers use read-only root filesystem
   - Only specific directories are writable

3. **Security Updates**
   ```bash
   # Regularly update base images
   docker pull python:3.12-slim
   docker compose build --no-cache
   ```

## 5. Database Security

### PostgreSQL Hardening

1. **Strong Passwords**
   - Use minimum 32-character passwords
   - Rotate passwords regularly

2. **Connection Limits**
   ```yaml
   # Already configured in docker compose.yml
   max_connections: 200
   ```

3. **SSL Connections**
   - Enable SSL for database connections in production

## 6. File Upload Security

### Upload Restrictions

```bash
# Configure in .env
MAX_UPLOAD_SIZE=10737418240  # 10GB
```

### File Type Validation

- Strict MIME type checking
- File extension validation
- Magic number verification

## 7. Rate Limiting

### API Rate Limits

Default rate limiting is configured:
- 100 requests per hour per IP
- 1000 requests per hour per API key

### Redis-based Rate Limiting

For production, use Redis for distributed rate limiting across multiple API instances.

## 8. Monitoring and Auditing

### Security Monitoring

1. **Enable Structured Logging**
   ```bash
   LOG_LEVEL=info
   ```

2. **Monitor Failed Authentication**
   - Track failed API key attempts
   - Alert on suspicious patterns

3. **Audit Admin Actions**
   - All admin endpoints are logged
   - Monitor cleanup and configuration changes

## 9. Secrets Management

### Best Practices

1. **Never Commit Secrets**
   - `.env` file is in `.gitignore`
   - Use environment variables for all secrets

2. **Use Secret Management Systems**
   - Consider HashiCorp Vault
   - AWS Secrets Manager
   - Kubernetes Secrets

3. **Rotate Secrets Regularly**
   - API keys every 90 days
   - Database passwords every 180 days

## 10. Security Headers

The following security headers are automatically applied:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000; includeSubDomains`
- `Content-Security-Policy: default-src 'self'`

## 11. Vulnerability Management

### Dependency Scanning

```bash
# Check for vulnerabilities
pip audit

# Update dependencies
pip install --upgrade -r requirements.txt
```

### Container Scanning

```bash
# Scan Docker images
docker scan rendiff-api:latest
```

## 12. Incident Response

### Security Incident Checklist

1. **Immediate Actions**
   - Revoke compromised API keys
   - Reset passwords if needed
   - Review access logs

2. **Investigation**
   - Check audit logs
   - Review recent changes
   - Identify scope of breach

3. **Remediation**
   - Patch vulnerabilities
   - Update security configurations
   - Notify affected users

## 13. Security Checklist

Before deploying to production:

- [ ] All default passwords changed
- [ ] Admin API keys generated and configured
- [ ] SSL/TLS enabled
- [ ] IP whitelisting configured (if needed)
- [ ] CORS origins restricted
- [ ] Rate limiting enabled
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Incident response plan documented
- [ ] Security headers verified
- [ ] Dependencies up to date
- [ ] Container images scanned

## Reporting Security Issues

If you discover a security vulnerability, please report it to:
- Email: security@example.com
- Do not create public GitHub issues for security vulnerabilities