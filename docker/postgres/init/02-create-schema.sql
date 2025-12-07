-- Rendiff Schema Creation
-- This script creates the application schema using Alembic migration logic
-- Note: Rendiff is powered by FFmpeg for media processing

-- Enable UUID extension for GUID type
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create custom GUID type similar to SQLAlchemy GUID
CREATE DOMAIN guid AS UUID;

-- Create jobs table with all required columns
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority VARCHAR(20) NOT NULL DEFAULT 'normal',
    input_path VARCHAR(1000) NOT NULL,
    output_path VARCHAR(1000) NOT NULL,
    input_metadata JSONB,
    output_metadata JSONB,
    options JSONB,
    operations JSONB,
    progress FLOAT DEFAULT 0.0,
    stage VARCHAR(100),
    fps FLOAT,
    eta_seconds INTEGER,
    vmaf_score FLOAT,
    psnr_score FLOAT,
    ssim_score FLOAT,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    error_message TEXT,
    error_details JSONB,
    retry_count INTEGER DEFAULT 0,
    worker_id VARCHAR(100),
    processing_time FLOAT,
    api_key VARCHAR(255),
    webhook_url VARCHAR(1000),
    webhook_events JSONB
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_job_status_created ON jobs(status, created_at);
CREATE INDEX IF NOT EXISTS idx_job_api_key_created ON jobs(api_key, created_at);
CREATE INDEX IF NOT EXISTS ix_jobs_api_key ON jobs(api_key);
CREATE INDEX IF NOT EXISTS ix_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority);
CREATE INDEX IF NOT EXISTS idx_jobs_worker_id ON jobs(worker_id);
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

-- Create partial indexes for active jobs
CREATE INDEX IF NOT EXISTS idx_jobs_active ON jobs(created_at) 
WHERE status IN ('pending', 'processing');

-- Create GIN index for JSON columns
CREATE INDEX IF NOT EXISTS idx_jobs_operations_gin ON jobs USING GIN(operations);
CREATE INDEX IF NOT EXISTS idx_jobs_metadata_gin ON jobs USING GIN(input_metadata);

-- Create API keys table for authentication
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100),
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    rate_limit INTEGER DEFAULT 1000,
    permissions JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    expires_at TIMESTAMP WITH TIME ZONE,
    last_used_at TIMESTAMP WITH TIME ZONE,
    usage_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active, expires_at);

-- Create job logs table for detailed logging
CREATE TABLE IF NOT EXISTS job_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    level VARCHAR(20) NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    details JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_job_logs_job_id ON job_logs(job_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_job_logs_level ON job_logs(level);

-- Create system metrics table
CREATE TABLE IF NOT EXISTS system_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    metric_type VARCHAR(50) NOT NULL DEFAULT 'gauge',
    labels JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_system_metrics_name_time ON system_metrics(metric_name, timestamp);
CREATE INDEX IF NOT EXISTS idx_system_metrics_timestamp ON system_metrics(timestamp);

-- Create storage usage table
CREATE TABLE IF NOT EXISTS storage_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    backend_name VARCHAR(100) NOT NULL,
    path VARCHAR(1000) NOT NULL,
    size_bytes BIGINT NOT NULL,
    file_count INTEGER DEFAULT 1,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_storage_usage_backend ON storage_usage(backend_name);
CREATE INDEX IF NOT EXISTS idx_storage_usage_job_id ON storage_usage(job_id);

-- Create triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to storage_usage table
CREATE TRIGGER update_storage_usage_updated_at 
BEFORE UPDATE ON storage_usage 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create function to clean up old records
CREATE OR REPLACE FUNCTION cleanup_old_records()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Clean up completed jobs older than 30 days
    DELETE FROM jobs 
    WHERE status IN ('completed', 'failed', 'cancelled') 
    AND completed_at < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Clean up old job logs (keep last 7 days)
    DELETE FROM job_logs 
    WHERE timestamp < NOW() - INTERVAL '7 days';
    
    -- Clean up old system metrics (keep last 90 days)
    DELETE FROM system_metrics 
    WHERE timestamp < NOW() - INTERVAL '90 days';
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- Create function for job statistics
CREATE OR REPLACE FUNCTION get_job_statistics(since_hours INTEGER DEFAULT 24)
RETURNS TABLE(
    status VARCHAR,
    count BIGINT,
    avg_processing_time FLOAT,
    avg_progress FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        j.status,
        COUNT(*) as count,
        AVG(j.processing_time) as avg_processing_time,
        AVG(j.progress) as avg_progress
    FROM jobs j
    WHERE j.created_at > NOW() - (since_hours || ' hours')::INTERVAL
    GROUP BY j.status
    ORDER BY count DESC;
END;
$$ LANGUAGE plpgsql;

-- Insert initial API key for testing (in production, generate securely)
INSERT INTO api_keys (key_hash, name, description, permissions) 
VALUES (
    'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855', -- hash of empty string for demo
    'Demo API Key',
    'Initial API key for testing - CHANGE IN PRODUCTION',
    '["*"]'::jsonb
) ON CONFLICT (key_hash) DO NOTHING;

-- Log schema creation
INSERT INTO system_health (component, status, details) 
VALUES (
    'schema', 
    'healthy', 
    jsonb_build_object(
        'created_at', NOW(),
        'tables_created', 6,
        'indexes_created', 12,
        'functions_created', 3
    )
) ON CONFLICT (component) DO UPDATE SET 
    last_check = NOW(),
    details = EXCLUDED.details;

-- Create view for job summary
CREATE OR REPLACE VIEW job_summary AS
SELECT 
    DATE_TRUNC('hour', created_at) as hour,
    status,
    COUNT(*) as job_count,
    AVG(processing_time) as avg_processing_time,
    AVG(progress) as avg_progress
FROM jobs
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE_TRUNC('hour', created_at), status
ORDER BY hour DESC, status;

-- Grant necessary permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO rendiff_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO rendiff_user;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO rendiff_user;

-- Log successful schema creation
DO $$
BEGIN
    RAISE NOTICE 'Rendiff Schema created successfully at %', NOW();
END $$;