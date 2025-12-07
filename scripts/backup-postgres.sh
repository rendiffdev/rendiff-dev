#!/bin/bash
# PostgreSQL Backup Script with S3 Upload
# Production-grade backup with encryption and retention

set -euo pipefail

# Configuration
BACKUP_DIR="${BACKUP_DIR:-/backup/postgres}"
S3_BUCKET="${S3_BUCKET:-rendiff-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
SLACK_WEBHOOK="${SLACK_WEBHOOK:-}"

# Database connection
DB_HOST="${POSTGRES_HOST:-postgres}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-rendiff}"
DB_USER="${POSTGRES_USER:-rendiff_user}"
export PGPASSWORD="${POSTGRES_PASSWORD}"

# Timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="rendiff_backup_${TIMESTAMP}"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

send_alert() {
    local status=$1
    local message=$2
    
    if [ -n "$SLACK_WEBHOOK" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"Backup $status: $message\"}" \
            "$SLACK_WEBHOOK" 2>/dev/null || true
    fi
}

# Pre-flight checks
check_requirements() {
    log "Checking requirements..."
    
    for cmd in pg_dump aws gpg gzip; do
        if ! command -v $cmd &> /dev/null; then
            error "$cmd is required but not installed"
            exit 1
        fi
    done
    
    # Check database connectivity
    if ! pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME"; then
        error "Cannot connect to database"
        exit 1
    fi
    
    # Check S3 access
    if ! aws s3 ls "s3://$S3_BUCKET" &> /dev/null; then
        error "Cannot access S3 bucket: $S3_BUCKET"
        exit 1
    fi
}

# Perform backup
perform_backup() {
    log "Starting backup of $DB_NAME..."
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    cd "$BACKUP_DIR"
    
    # Dump database with parallel jobs
    log "Dumping database..."
    pg_dump \
        -h "$DB_HOST" \
        -p "$DB_PORT" \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --format=custom \
        --verbose \
        --no-password \
        --jobs=4 \
        --file="${BACKUP_NAME}.dump" \
        2>&1 | tee "${BACKUP_NAME}.log"
    
    # Verify dump
    log "Verifying backup..."
    pg_restore --list "${BACKUP_NAME}.dump" > /dev/null
    
    # Get backup size
    BACKUP_SIZE=$(du -h "${BACKUP_NAME}.dump" | cut -f1)
    log "Backup size: $BACKUP_SIZE"
    
    # Compress backup
    log "Compressing backup..."
    gzip -9 "${BACKUP_NAME}.dump"
    
    # Encrypt if key provided
    if [ -n "$ENCRYPTION_KEY" ]; then
        log "Encrypting backup..."
        echo "$ENCRYPTION_KEY" | gpg --batch --yes --passphrase-fd 0 \
            --cipher-algo AES256 \
            --symmetric \
            --output "${BACKUP_NAME}.dump.gz.gpg" \
            "${BACKUP_NAME}.dump.gz"
        rm "${BACKUP_NAME}.dump.gz"
        BACKUP_FILE="${BACKUP_NAME}.dump.gz.gpg"
    else
        BACKUP_FILE="${BACKUP_NAME}.dump.gz"
    fi
}

# Upload to S3
upload_to_s3() {
    log "Uploading to S3..."
    
    # Upload with metadata
    aws s3 cp "$BACKUP_FILE" "s3://$S3_BUCKET/postgres/$BACKUP_FILE" \
        --storage-class STANDARD_IA \
        --metadata "timestamp=$TIMESTAMP,database=$DB_NAME,size=$BACKUP_SIZE" \
        --only-show-errors
    
    # Upload log file
    aws s3 cp "${BACKUP_NAME}.log" "s3://$S3_BUCKET/postgres/logs/${BACKUP_NAME}.log" \
        --only-show-errors
    
    # Verify upload
    if aws s3 ls "s3://$S3_BUCKET/postgres/$BACKUP_FILE" &> /dev/null; then
        log "Upload successful"
    else
        error "Upload verification failed"
        return 1
    fi
}

# Clean up old backups
cleanup_old_backups() {
    log "Cleaning up old backups (retention: $RETENTION_DAYS days)..."
    
    # Local cleanup
    find "$BACKUP_DIR" -name "*.dump.gz*" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    find "$BACKUP_DIR" -name "*.log" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true
    
    # S3 lifecycle rules should handle S3 cleanup, but we can also do it here
    CUTOFF_DATE=$(date -d "$RETENTION_DAYS days ago" +%Y-%m-%d)
    
    aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "postgres/" \
        --query "Contents[?LastModified<='$CUTOFF_DATE'].Key" \
        --output text | \
    while read -r key; do
        if [ -n "$key" ]; then
            log "Deleting old backup: $key"
            aws s3 rm "s3://$S3_BUCKET/$key" --only-show-errors
        fi
    done
}

# Create backup manifest
create_manifest() {
    log "Creating backup manifest..."
    
    cat > "${BACKUP_NAME}.manifest.json" <<EOF
{
    "timestamp": "$TIMESTAMP",
    "database": "$DB_NAME",
    "host": "$DB_HOST",
    "size": "$BACKUP_SIZE",
    "compressed_file": "$BACKUP_FILE",
    "encrypted": $([ -n "$ENCRYPTION_KEY" ] && echo "true" || echo "false"),
    "retention_days": $RETENTION_DAYS,
    "pg_version": "$(pg_dump --version | head -1)",
    "schema_version": "$(psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c 'SELECT MAX(version_num) FROM alembic_version;' 2>/dev/null || echo 'unknown')"
}
EOF
    
    # Upload manifest
    aws s3 cp "${BACKUP_NAME}.manifest.json" "s3://$S3_BUCKET/postgres/manifests/${BACKUP_NAME}.manifest.json" \
        --only-show-errors
}

# Main execution
main() {
    log "=== PostgreSQL Backup Script ==="
    log "Database: $DB_NAME"
    log "Backup location: s3://$S3_BUCKET/postgres/"
    
    # Trap errors
    trap 'error "Backup failed"; send_alert "FAILED" "Database backup failed for $DB_NAME"; exit 1' ERR
    
    # Execute backup steps
    check_requirements
    perform_backup
    upload_to_s3
    create_manifest
    cleanup_old_backups
    
    # Clean up local files
    log "Cleaning up local files..."
    rm -f "${BACKUP_NAME}".*
    
    # Success notification
    log "Backup completed successfully!"
    send_alert "SUCCESS" "Database backup completed for $DB_NAME (Size: $BACKUP_SIZE)"
    
    # Output for automation
    echo "BACKUP_FILE=$BACKUP_FILE"
    echo "BACKUP_LOCATION=s3://$S3_BUCKET/postgres/$BACKUP_FILE"
}

# Run main function
main "$@"