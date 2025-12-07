#!/bin/bash
# Disaster Recovery Script for FFmpeg API
# Automated recovery from backups with validation

set -euo pipefail

# Configuration
S3_BUCKET="${S3_BUCKET:-rendiff-backups}"
RESTORE_DIR="${RESTORE_DIR:-/tmp/restore}"
TARGET_DB_HOST="${TARGET_DB_HOST:-postgres}"
TARGET_DB_PORT="${TARGET_DB_PORT:-5432}"
TARGET_DB_NAME="${TARGET_DB_NAME:-rendiff}"
TARGET_DB_USER="${TARGET_DB_USER:-rendiff_user}"
export PGPASSWORD="${POSTGRES_PASSWORD}"

# Recovery options
RECOVERY_MODE="${RECOVERY_MODE:-latest}"  # latest, specific, point-in-time
RECOVERY_TIMESTAMP="${RECOVERY_TIMESTAMP:-}"
ENCRYPTION_KEY="${BACKUP_ENCRYPTION_KEY:-}"
VERIFY_ONLY="${VERIFY_ONLY:-false}"

# Logging
log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Find available backups
list_backups() {
    log "Listing available backups..."
    
    aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "postgres/rendiff_backup_" \
        --query "Contents[?ends_with(Key, '.dump.gz') || ends_with(Key, '.dump.gz.gpg')].[Key,LastModified,Size]" \
        --output table
}

# Get latest backup
get_latest_backup() {
    aws s3api list-objects-v2 \
        --bucket "$S3_BUCKET" \
        --prefix "postgres/rendiff_backup_" \
        --query "Contents[?ends_with(Key, '.dump.gz') || ends_with(Key, '.dump.gz.gpg')] | sort_by(@, &LastModified) | [-1].Key" \
        --output text
}

# Download backup
download_backup() {
    local backup_key=$1
    local backup_file=$(basename "$backup_key")
    
    log "Downloading backup: $backup_key"
    mkdir -p "$RESTORE_DIR"
    
    aws s3 cp "s3://$S3_BUCKET/$backup_key" "$RESTORE_DIR/$backup_file" \
        --only-show-errors
    
    # Download manifest if exists
    local manifest_key="${backup_key%.dump.gz*}.manifest.json"
    manifest_key="postgres/manifests/$(basename "$manifest_key")"
    
    if aws s3 ls "s3://$S3_BUCKET/$manifest_key" &> /dev/null; then
        log "Downloading manifest..."
        aws s3 cp "s3://$S3_BUCKET/$manifest_key" "$RESTORE_DIR/" --only-show-errors
        
        # Display manifest info
        log "Backup information:"
        jq . "$RESTORE_DIR/$(basename "$manifest_key")"
    fi
    
    echo "$backup_file"
}

# Decrypt backup if needed
decrypt_backup() {
    local backup_file=$1
    
    if [[ $backup_file == *.gpg ]]; then
        if [ -z "$ENCRYPTION_KEY" ]; then
            error "Backup is encrypted but no encryption key provided"
            exit 1
        fi
        
        log "Decrypting backup..."
        local decrypted_file="${backup_file%.gpg}"
        
        echo "$ENCRYPTION_KEY" | gpg --batch --yes --passphrase-fd 0 \
            --decrypt "$RESTORE_DIR/$backup_file" > "$RESTORE_DIR/$decrypted_file"
        
        rm "$RESTORE_DIR/$backup_file"
        echo "$decrypted_file"
    else
        echo "$backup_file"
    fi
}

# Decompress backup
decompress_backup() {
    local backup_file=$1
    
    log "Decompressing backup..."
    gunzip "$RESTORE_DIR/$backup_file"
    
    echo "${backup_file%.gz}"
}

# Verify backup integrity
verify_backup() {
    local dump_file=$1
    
    log "Verifying backup integrity..."
    
    if pg_restore --list "$RESTORE_DIR/$dump_file" > /dev/null 2>&1; then
        log "Backup verification passed"
        
        # Count objects
        local table_count=$(pg_restore --list "$RESTORE_DIR/$dump_file" | grep -c "TABLE DATA" || true)
        local index_count=$(pg_restore --list "$RESTORE_DIR/$dump_file" | grep -c "INDEX" || true)
        log "Found $table_count tables and $index_count indexes"
        
        return 0
    else
        error "Backup verification failed"
        return 1
    fi
}

# Prepare target database
prepare_database() {
    log "Preparing target database..."
    
    # Check if database exists
    if psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$TARGET_DB_NAME"; then
        log "Target database exists"
        
        if [ "$VERIFY_ONLY" != "true" ]; then
            read -p "Database $TARGET_DB_NAME exists. Drop and recreate? (y/N) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                log "Dropping existing database..."
                psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -c "DROP DATABASE IF EXISTS $TARGET_DB_NAME;"
                psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -c "CREATE DATABASE $TARGET_DB_NAME OWNER $TARGET_DB_USER;"
            else
                log "Aborting restore"
                exit 1
            fi
        fi
    else
        log "Creating target database..."
        psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -c "CREATE DATABASE $TARGET_DB_NAME OWNER $TARGET_DB_USER;"
    fi
}

# Restore database
restore_database() {
    local dump_file=$1
    
    log "Starting database restore..."
    
    # Create restore script
    cat > "$RESTORE_DIR/restore.sh" <<'EOF'
#!/bin/bash
set -e
pg_restore \
    --host="$1" \
    --port="$2" \
    --username="$3" \
    --dbname="$4" \
    --no-password \
    --verbose \
    --clean \
    --if-exists \
    --no-owner \
    --no-privileges \
    --jobs=4 \
    "$5" 2>&1 | while read line; do
        echo "[RESTORE] $line"
    done
EOF
    chmod +x "$RESTORE_DIR/restore.sh"
    
    # Execute restore
    if "$RESTORE_DIR/restore.sh" "$TARGET_DB_HOST" "$TARGET_DB_PORT" "$TARGET_DB_USER" "$TARGET_DB_NAME" "$RESTORE_DIR/$dump_file"; then
        log "Database restore completed successfully"
    else
        error "Database restore failed"
        return 1
    fi
}

# Post-restore validation
validate_restore() {
    log "Validating restored database..."
    
    # Check table counts
    local table_count=$(psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -d "$TARGET_DB_NAME" -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';")
    log "Restored tables: $table_count"
    
    # Check critical tables
    for table in jobs api_keys alembic_version; do
        if psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -d "$TARGET_DB_NAME" -c "SELECT 1 FROM $table LIMIT 1;" &> /dev/null; then
            log "✓ Table $table exists and is accessible"
        else
            error "✗ Table $table is missing or inaccessible"
        fi
    done
    
    # Check row counts
    log "Row counts:"
    psql -h "$TARGET_DB_HOST" -p "$TARGET_DB_PORT" -U "$TARGET_DB_USER" -d "$TARGET_DB_NAME" <<EOF
SELECT 'jobs' as table_name, COUNT(*) as row_count FROM jobs
UNION ALL
SELECT 'api_keys', COUNT(*) FROM api_keys;
EOF
}

# Recovery plan
create_recovery_plan() {
    log "Creating recovery plan..."
    
    cat > "$RESTORE_DIR/recovery-plan.md" <<EOF
# FFmpeg API Disaster Recovery Plan

## Recovery Information
- **Date**: $(date)
- **Backup Used**: $1
- **Target Database**: $TARGET_DB_HOST:$TARGET_DB_PORT/$TARGET_DB_NAME
- **Recovery Mode**: $RECOVERY_MODE

## Pre-Recovery Checklist
- [ ] Verify backup integrity
- [ ] Ensure target database is accessible
- [ ] Stop application services
- [ ] Notify team of maintenance window

## Recovery Steps
1. Download backup from S3
2. Decrypt backup (if encrypted)
3. Decompress backup
4. Verify backup integrity
5. Prepare target database
6. Restore database
7. Validate restoration
8. Update application configuration
9. Restart application services
10. Verify application functionality

## Post-Recovery Checklist
- [ ] Verify all tables restored
- [ ] Check application connectivity
- [ ] Run smoke tests
- [ ] Monitor for errors
- [ ] Document any issues

## Rollback Plan
If recovery fails:
1. Restore from previous known-good backup
2. Use read replica if available
3. Contact database administrator

## Contact Information
- DBA Team: dba@company.com
- On-Call: oncall@company.com
- Escalation: manager@company.com
EOF
    
    log "Recovery plan saved to: $RESTORE_DIR/recovery-plan.md"
}

# Main recovery function
main() {
    log "=== FFmpeg API Disaster Recovery ==="
    log "Target: $TARGET_DB_HOST:$TARGET_DB_PORT/$TARGET_DB_NAME"
    log "Mode: $RECOVERY_MODE"
    
    # Determine backup to use
    local backup_key
    case "$RECOVERY_MODE" in
        latest)
            backup_key=$(get_latest_backup)
            ;;
        specific)
            if [ -z "$RECOVERY_TIMESTAMP" ]; then
                error "RECOVERY_TIMESTAMP required for specific recovery mode"
                exit 1
            fi
            backup_key="postgres/rendiff_backup_${RECOVERY_TIMESTAMP}.dump.gz"
            ;;
        list)
            list_backups
            exit 0
            ;;
        *)
            error "Invalid recovery mode: $RECOVERY_MODE"
            exit 1
            ;;
    esac
    
    if [ -z "$backup_key" ] || [ "$backup_key" == "None" ]; then
        error "No backup found"
        exit 1
    fi
    
    log "Selected backup: $backup_key"
    
    # Download and prepare backup
    local backup_file=$(download_backup "$backup_key")
    backup_file=$(decrypt_backup "$backup_file")
    backup_file=$(decompress_backup "$backup_file")
    
    # Verify backup
    verify_backup "$backup_file"
    
    if [ "$VERIFY_ONLY" == "true" ]; then
        log "Verification only mode - skipping restore"
        create_recovery_plan "$backup_key"
        exit 0
    fi
    
    # Restore database
    prepare_database
    restore_database "$backup_file"
    validate_restore
    
    # Create recovery documentation
    create_recovery_plan "$backup_key"
    
    # Cleanup
    log "Cleaning up temporary files..."
    rm -rf "$RESTORE_DIR"
    
    log "Disaster recovery completed successfully!"
    log "Please verify application functionality before resuming operations"
}

# Run main function
main "$@"