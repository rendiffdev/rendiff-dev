-- Rendiff Database Initialization Script
-- This script runs automatically when PostgreSQL container starts for the first time
-- Note: Rendiff is powered by FFmpeg for media processing

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Create additional database if needed for testing
-- CREATE DATABASE rendiff_test OWNER rendiff_user;

-- Grant additional permissions
GRANT ALL PRIVILEGES ON DATABASE rendiff TO rendiff_user;

-- Create schemas (if needed for multi-tenancy in future)
-- CREATE SCHEMA IF NOT EXISTS api AUTHORIZATION rendiff_user;
-- CREATE SCHEMA IF NOT EXISTS analytics AUTHORIZATION rendiff_user;

-- Ensure user has necessary permissions
ALTER USER rendiff_user CREATEDB;
ALTER USER rendiff_user WITH SUPERUSER;

-- Set default settings
ALTER DATABASE rendiff SET timezone TO 'UTC';
ALTER DATABASE rendiff SET log_statement TO 'all';
ALTER DATABASE rendiff SET log_min_duration_statement TO 1000;

-- Performance optimizations for video processing workloads
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET track_activities = on;
ALTER SYSTEM SET track_counts = on;
ALTER SYSTEM SET track_io_timing = on;
ALTER SYSTEM SET track_functions = 'all';

-- Reload configuration
SELECT pg_reload_conf();

-- Create initial monitoring table for health checks
CREATE TABLE IF NOT EXISTS system_health (
    id SERIAL PRIMARY KEY,
    component VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'healthy',
    last_check TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    details JSONB,
    UNIQUE(component)
);

-- Insert initial health check record
INSERT INTO system_health (component, status, details) 
VALUES ('database', 'healthy', '{"initialized_at": "' || NOW() || '"}')
ON CONFLICT (component) DO UPDATE SET 
    last_check = NOW(),
    details = EXCLUDED.details;

-- Create function for health check
CREATE OR REPLACE FUNCTION check_database_health()
RETURNS TABLE(component TEXT, status TEXT, details JSONB) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'database'::TEXT,
        'healthy'::TEXT,
        jsonb_build_object(
            'connections', (SELECT count(*) FROM pg_stat_activity),
            'database_size', pg_size_pretty(pg_database_size(current_database())),
            'uptime', date_trunc('second', NOW() - pg_postmaster_start_time()),
            'version', version()
        );
END;
$$ LANGUAGE plpgsql;

-- Log successful initialization
DO $$
BEGIN
    RAISE NOTICE 'Rendiff Database initialized successfully at %', NOW();
END $$;