#!/bin/bash
# Automated database backup script for production
# Supports PostgreSQL with encryption, compression, and AWS S3 storage

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Load environment variables
if [ -f "$PROJECT_ROOT/.env" ]; then
    source "$PROJECT_ROOT/.env"
fi

# Default configuration
BACKUP_DIR="${BACKUP_DIR:-/var/backups/rendiff}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
BACKUP_ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
AWS_S3_BUCKET="${AWS_S3_BUCKET:-}"
NOTIFICATION_WEBHOOK="${NOTIFICATION_WEBHOOK:-}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

# Database configuration
DB_HOST="${DATABASE_HOST:-localhost}"
DB_PORT="${DATABASE_PORT:-5432}"
DB_NAME="${DATABASE_NAME:-rendiff}"
DB_USER="${DATABASE_USER:-postgres}"
DB_PASSWORD="${DATABASE_PASSWORD:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        ERROR)
            echo -e "${RED}[${timestamp}] ERROR: ${message}${NC}" >&2
            ;;
        WARN)
            echo -e "${YELLOW}[${timestamp}] WARN: ${message}${NC}" >&2
            ;;
        INFO)
            echo -e "${GREEN}[${timestamp}] INFO: ${message}${NC}"
            ;;
        DEBUG)
            if [ "$LOG_LEVEL" = "DEBUG" ]; then
                echo -e "${BLUE}[${timestamp}] DEBUG: ${message}${NC}"
            fi
            ;;
    esac
}

# Error handling
error_exit() {
    log ERROR "$1"
    send_notification "FAILURE" "$1"
    exit 1
}

# Send notification
send_notification() {
    local status="$1"
    local message="$2"
    
    if [ -n "$NOTIFICATION_WEBHOOK" ]; then
        curl -X POST "$NOTIFICATION_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"text\":\"[FFmpeg API Backup] $status: $message\"}" \
            || log WARN "Failed to send notification"
    fi
}

# Check prerequisites
check_prerequisites() {
    log INFO "Checking prerequisites..."
    
    # Check required commands
    local required_commands="pg_dump gzip"
    for cmd in $required_commands; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "Required command '$cmd' not found"
        fi
    done
    
    # Check optional commands
    if [ -n "$BACKUP_ENCRYPTION_KEY" ]; then
        if ! command -v gpg &> /dev/null; then
            error_exit "GPG is required for encryption but not found"
        fi
    fi
    
    if [ -n "$AWS_S3_BUCKET" ]; then
        if ! command -v aws &> /dev/null; then
            error_exit "AWS CLI is required for S3 upload but not found"
        fi
    fi
    
    # Check database connectivity
    if ! PGPASSWORD="$DB_PASSWORD" pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" &> /dev/null; then
        error_exit "Cannot connect to database $DB_HOST:$DB_PORT"
    fi
    
    log INFO "Prerequisites check passed"
}

# Create backup directory
create_backup_directory() {
    log INFO "Creating backup directory..."
    
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR" || error_exit "Failed to create backup directory: $BACKUP_DIR"
        log INFO "Created backup directory: $BACKUP_DIR"
    fi
    
    # Set proper permissions
    chmod 700 "$BACKUP_DIR" || error_exit "Failed to set permissions on backup directory"
}

# Generate backup filename
generate_backup_filename() {
    local timestamp=$(date '+%Y%m%d_%H%M%S')
    local hostname=$(hostname -s)
    echo "${DB_NAME}_${hostname}_${timestamp}.sql"
}

# Perform database backup
perform_backup() {
    local backup_file="$1"
    local backup_path="$BACKUP_DIR/$backup_file"
    
    log INFO "Starting database backup..."
    log DEBUG "Backup file: $backup_path"
    
    # Create backup with compression
    if PGPASSWORD="$DB_PASSWORD" pg_dump \
        --host="$DB_HOST" \
        --port="$DB_PORT" \
        --username="$DB_USER" \
        --dbname="$DB_NAME" \
        --format=custom \
        --compress=9 \
        --verbose \
        --no-password \
        --file="$backup_path" 2>&1 | grep -v "^$"; then
        
        log INFO "Database backup completed successfully"
    else
        error_exit "Database backup failed"
    fi
    
    # Verify backup file
    if [ ! -f "$backup_path" ] || [ ! -s "$backup_path" ]; then
        error_exit "Backup file is empty or missing: $backup_path"
    fi
    
    local backup_size=$(du -h "$backup_path" | cut -f1)
    log INFO "Backup size: $backup_size"
    
    echo "$backup_path"
}

# Encrypt backup
encrypt_backup() {
    local backup_path="$1"
    local encrypted_path="${backup_path}.gpg"
    
    if [ -n "$BACKUP_ENCRYPTION_KEY" ]; then
        log INFO "Encrypting backup..."
        
        if gpg --batch --yes --trust-model always \
            --cipher-algo AES256 \
            --compress-algo 2 \
            --recipient "$BACKUP_ENCRYPTION_KEY" \
            --output "$encrypted_path" \
            --encrypt "$backup_path"; then
            
            log INFO "Backup encrypted successfully"
            
            # Remove unencrypted backup
            rm "$backup_path" || log WARN "Failed to remove unencrypted backup"
            
            echo "$encrypted_path"
        else
            error_exit "Failed to encrypt backup"
        fi
    else
        echo "$backup_path"
    fi
}

# Upload to S3
upload_to_s3() {
    local backup_path="$1"
    local backup_file=$(basename "$backup_path")
    
    if [ -n "$AWS_S3_BUCKET" ]; then
        log INFO "Uploading backup to S3..."
        
        local s3_key="database-backups/$(date '+%Y/%m/%d')/$backup_file"
        
        if aws s3 cp "$backup_path" "s3://$AWS_S3_BUCKET/$s3_key" \
            --storage-class STANDARD_IA \
            --server-side-encryption AES256; then
            
            log INFO "Backup uploaded to S3: s3://$AWS_S3_BUCKET/$s3_key"
            
            # Set lifecycle policy for automatic cleanup
            aws s3api put-object-tagging \
                --bucket "$AWS_S3_BUCKET" \
                --key "$s3_key" \
                --tagging "TagSet=[{Key=Type,Value=DatabaseBackup},{Key=RetentionDays,Value=$BACKUP_RETENTION_DAYS}]" \
                || log WARN "Failed to set S3 object tags"
        else
            error_exit "Failed to upload backup to S3"
        fi
    fi
}

# Clean old backups
cleanup_old_backups() {
    log INFO "Cleaning up old backups..."
    
    # Local cleanup
    find "$BACKUP_DIR" -name "${DB_NAME}_*.sql*" -type f -mtime +$BACKUP_RETENTION_DAYS -delete \
        || log WARN "Failed to clean up old local backups"
    
    local cleaned_count=$(find "$BACKUP_DIR" -name "${DB_NAME}_*.sql*" -type f -mtime +$BACKUP_RETENTION_DAYS -print | wc -l)
    if [ $cleaned_count -gt 0 ]; then
        log INFO "Cleaned up $cleaned_count old local backups"
    fi
    
    # S3 cleanup (if configured)
    if [ -n "$AWS_S3_BUCKET" ]; then
        local cutoff_date=$(date -d "$BACKUP_RETENTION_DAYS days ago" '+%Y-%m-%d')
        
        aws s3api list-objects-v2 \
            --bucket "$AWS_S3_BUCKET" \
            --prefix "database-backups/" \
            --query "Contents[?LastModified<='$cutoff_date'][].Key" \
            --output text | \
        while read -r key; do
            if [ -n "$key" ]; then
                aws s3 rm "s3://$AWS_S3_BUCKET/$key" \
                    || log WARN "Failed to delete old S3 backup: $key"
            fi
        done
    fi
}

# Verify backup integrity
verify_backup() {
    local backup_path="$1"
    
    log INFO "Verifying backup integrity..."
    
    # For encrypted backups, we can't easily verify without decrypting
    if [[ "$backup_path" == *.gpg ]]; then
        log INFO "Backup is encrypted, skipping content verification"
        return 0
    fi
    
    # Verify backup can be read by pg_restore
    if pg_restore --list "$backup_path" &> /dev/null; then
        log INFO "Backup integrity verified"
        return 0
    else
        error_exit "Backup integrity check failed"
    fi
}

# Generate backup report
generate_report() {
    local backup_path="$1"
    local backup_file=$(basename "$backup_path")
    local backup_size=$(du -h "$backup_path" | cut -f1)
    local backup_date=$(date '+%Y-%m-%d %H:%M:%S')
    
    cat > "$BACKUP_DIR/backup_report.json" << EOF
{
    "backup_date": "$backup_date",
    "backup_file": "$backup_file",
    "backup_size": "$backup_size",
    "backup_path": "$backup_path",
    "database": {
        "host": "$DB_HOST",
        "port": "$DB_PORT",
        "name": "$DB_NAME",
        "user": "$DB_USER"
    },
    "encryption": $([ -n "$BACKUP_ENCRYPTION_KEY" ] && echo "true" || echo "false"),
    "s3_upload": $([ -n "$AWS_S3_BUCKET" ] && echo "true" || echo "false"),
    "status": "success"
}
EOF
    
    log INFO "Backup report generated: $BACKUP_DIR/backup_report.json"
}

# Main backup function
main() {
    log INFO "Starting FFmpeg API database backup..."
    
    # Check prerequisites
    check_prerequisites
    
    # Create backup directory
    create_backup_directory
    
    # Generate backup filename
    local backup_file=$(generate_backup_filename)
    
    # Perform backup
    local backup_path=$(perform_backup "$backup_file")
    
    # Encrypt backup if configured
    backup_path=$(encrypt_backup "$backup_path")
    
    # Verify backup integrity
    verify_backup "$backup_path"
    
    # Upload to S3 if configured
    upload_to_s3 "$backup_path"
    
    # Clean old backups
    cleanup_old_backups
    
    # Generate report
    generate_report "$backup_path"
    
    log INFO "Backup completed successfully: $backup_path"
    send_notification "SUCCESS" "Database backup completed successfully"
}

# Handle script termination
trap 'log ERROR "Backup script interrupted"; send_notification "FAILURE" "Backup script interrupted"; exit 1' INT TERM

# Run main function
main "$@"