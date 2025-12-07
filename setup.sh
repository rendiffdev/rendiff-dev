#!/bin/bash

# Rendiff - Simple Setup Script
# A REST API layer powered by FFmpeg for media processing
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "🚀 Rendiff Setup (Powered by FFmpeg)"
echo "======================================"

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTION]"
    echo ""
    echo "🚀 Rendiff - Production-Ready Setup Script (Powered by FFmpeg)"
    echo ""
    echo "Deployment Options:"
    echo "  --development    🛠️  Fast local development (SQLite, debug mode, no auth)"
    echo "  --standard       🏭 Production CPU setup (PostgreSQL, Redis, monitoring)"
    echo "  --gpu            🎮 GPU-accelerated setup (NVIDIA hardware acceleration)"
    echo ""
    echo "Management Options:"
    echo "  --status         📊 Show current deployment status"
    echo "  --stop           🛑 Stop all running services"
    echo "  --clean          🧹 Complete cleanup (stops services, removes volumes)"
    echo "  --help           📖 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 --development     # Quick 60-second setup for local development"
    echo "  $0 --standard        # Production setup with PostgreSQL and monitoring"
    echo "  $0 --gpu            # GPU setup with NVIDIA acceleration"
    echo "  $0 --status         # Check what's currently running"
    echo ""
    echo "🌐 Access URLs (when running):"
    echo "  • API:        http://localhost:8000"
    echo "  • Docs:       http://localhost:8000/docs"
    echo "  • Health:     http://localhost:8000/api/v1/health"
    echo "  • Prometheus: http://localhost:9090 (standard/gpu only)"
    echo "  • Grafana:    http://localhost:3000 (standard/gpu only)"
    echo ""
    exit 1
}

# Function to check requirements
check_requirements() {
    echo "Checking requirements..."
    
    if ! command -v docker &> /dev/null; then
        echo "❌ Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
        echo "❌ Docker Compose is not available. Please install Docker Compose."
        exit 1
    fi
    
    echo "✅ Docker and Docker Compose are available"
}

# Function for development setup
setup_development() {
    echo "🛠️  Setting up Development Environment..."
    
    # Create development environment file
    cat > .env.dev << EOF
# Development Configuration - Fast Local Setup
DEBUG=true
TESTING=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=debug
API_WORKERS=1

# Database (SQLite for simplicity)
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db

# Queue (Redis)
REDIS_URL=redis://redis:6379/0

# Storage
STORAGE_PATH=./storage
TEMP_PATH=/tmp/rendiff

# Security (Disabled for development)
ENABLE_API_KEYS=false
ENABLE_RATE_LIMITING=false
API_CORS_ORIGINS=http://localhost:8000,http://127.0.0.1:8000,http://localhost:3000

# FFmpeg
FFMPEG_HARDWARE_ACCELERATION=auto
FFMPEG_THREADS=2

# Worker
WORKER_CONCURRENCY=2

# Development passwords
POSTGRES_PASSWORD=dev_password_123
GRAFANA_PASSWORD=admin
EOF

    ln -sf .env.dev .env
    
    echo "📁 Creating directories..."
    mkdir -p storage data logs config

    echo "🐳 Starting development services..."
    docker compose up -d redis api

    echo ""
    echo "✅ Development setup complete!"
    echo ""
    echo "🌐 API available at: http://localhost:8000"
    echo "📚 API docs at: http://localhost:8000/docs"
    echo "🔍 Health check: http://localhost:8000/api/v1/health"
    echo ""
    echo "📝 To stop: ./setup.sh --stop"
}

# Function for standard production setup
setup_standard() {
    echo "🏭 Setting up Standard Production Environment..."
    
    # Check if .env.example exists
    if [ ! -f ".env.example" ]; then
        echo "❌ .env.example not found! Please ensure it exists."
        exit 1
    fi
    
    # Create production environment file
    if [ ! -f ".env" ]; then
        echo "📋 Creating production .env file from template..."
        cp .env.example .env
        echo ""
        echo "⚠️  IMPORTANT: Edit .env file with your production values:"
        echo "   - Set secure passwords for POSTGRES_PASSWORD and GRAFANA_PASSWORD"
        echo "   - Configure API_CORS_ORIGINS for your domain"
        echo "   - Set ADMIN_API_KEYS for API access"
        echo ""
        read -p "Press Enter after editing .env file..."
    fi
    
    echo "📁 Creating directories..."
    mkdir -p storage data/postgres data/redis data/prometheus data/grafana logs config
    
    echo "🐳 Starting production services..."
    COMPOSE_PROFILES=standard docker compose up -d
    
    echo ""
    echo "✅ Standard production setup complete!"
    echo ""
    echo "🌐 API available at: http://localhost:8000"
    echo "📚 API docs at: http://localhost:8000/docs"
    echo "📊 Prometheus at: http://localhost:9090"
    echo "📈 Grafana at: http://localhost:3000"
    echo ""
    echo "📝 To stop: ./setup.sh --stop"
}

# Function for GPU-accelerated setup
setup_gpu() {
    echo "🎮 Setting up GPU-Accelerated Environment..."
    
    # Check for NVIDIA Docker runtime
    if ! docker info 2>/dev/null | grep -q nvidia; then
        echo "⚠️  NVIDIA Docker runtime not detected."
        echo "📖 For GPU acceleration, install:"
        echo "   1. NVIDIA drivers"
        echo "   2. NVIDIA Container Toolkit"
        echo "   3. Configure Docker to use nvidia runtime"
        echo ""
        read -p "Continue anyway? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # Check if .env.example exists
    if [ ! -f ".env.example" ]; then
        echo "❌ .env.example not found! Please ensure it exists."
        exit 1
    fi
    
    # Create GPU environment file
    if [ ! -f ".env" ]; then
        echo "📋 Creating GPU .env file from template..."
        cp .env.example .env
        echo ""
        echo "⚠️  IMPORTANT: Edit .env file with your production values and GPU settings:"
        echo "   - Set secure passwords"
        echo "   - Configure API_CORS_ORIGINS for your domain"  
        echo "   - Set ADMIN_API_KEYS for API access"
        echo "   - Verify GPU worker settings"
        echo ""
        read -p "Press Enter after editing .env file..."
    fi
    
    echo "📁 Creating directories..."
    mkdir -p storage data/postgres data/redis data/prometheus data/grafana logs config
    
    echo "🐳 Starting GPU-accelerated services..."
    COMPOSE_PROFILES=gpu,monitoring docker compose up -d
    
    echo ""
    echo "✅ GPU-accelerated setup complete!"
    echo ""
    echo "🌐 API available at: http://localhost:8000"
    echo "📚 API docs at: http://localhost:8000/docs"
    echo "📊 Prometheus at: http://localhost:9090"
    echo "📈 Grafana at: http://localhost:3000"
    echo "🎮 GPU workers enabled for hardware acceleration"
    echo ""
    echo "📝 To stop: ./setup.sh --stop"
}

# Function to show status
show_status() {
    echo "📊 Current Status:"
    echo "=================="
    
    # Check which environment is running
    if docker compose ps 2>/dev/null | grep -q "Up"; then
        echo "🟢 FFmpeg API is running"
        echo ""
        docker compose ps
        echo ""
        echo "🌐 Access URLs:"
        echo "   API: http://localhost:8000"
        echo "   Docs: http://localhost:8000/docs"
        echo "   Health: http://localhost:8000/api/v1/health"
        
        # Check if monitoring is enabled
        if docker compose ps prometheus 2>/dev/null | grep -q "Up"; then
            echo "   Prometheus: http://localhost:9090"
        fi
        if docker compose ps grafana 2>/dev/null | grep -q "Up"; then
            echo "   Grafana: http://localhost:3000"
        fi
        
        # Check active profiles
        if [ -f ".env" ]; then
            echo ""
            echo "📋 Current Configuration:"
            if grep -q "DEBUG=true" .env 2>/dev/null; then
                echo "   Mode: Development"
            else
                echo "   Mode: Production"
            fi
            
            if docker compose ps worker-gpu 2>/dev/null | grep -q "Up"; then
                echo "   GPU: Enabled"
            else
                echo "   GPU: Disabled"
            fi
        fi
        
    else
        echo "🔴 FFmpeg API is not running"
        echo ""
        echo "🚀 To start:"
        echo "   Development: ./setup.sh --development"
        echo "   Production:  ./setup.sh --standard"
        echo "   GPU:         ./setup.sh --gpu"
    fi
}

# Function to stop services
stop_services() {
    echo "🛑 Stopping services..."
    
    # Stop all possible configurations
    docker compose down --remove-orphans 2>/dev/null || true
    
    # Clean up development files
    if [ -f "compose.dev.yml" ]; then
        docker compose -f compose.dev.yml down 2>/dev/null || true
        rm -f compose.dev.yml
    fi
    
    # Clean up environment symlinks
    if [ -L ".env" ]; then
        rm -f .env
    fi
    
    echo "✅ Services stopped and cleaned up"
}

# Function to clean up everything
cleanup_all() {
    echo "🧹 Cleaning up everything..."
    
    stop_services
    
    echo "🗑️  Removing volumes..."
    docker volume prune -f 2>/dev/null || true
    
    echo "🗑️  Removing temporary files..."
    rm -rf data/ logs/ .env.dev compose.dev.yml 2>/dev/null || true
    
    echo "✅ Complete cleanup finished"
}

# Parse command line arguments
case "${1:-}" in
    --development|--dev)
        check_requirements
        setup_development
        ;;
    --standard|--prod)
        check_requirements
        setup_standard
        ;;
    --gpu|--hardware)
        check_requirements
        setup_gpu
        ;;
    --status)
        show_status
        ;;
    --stop)
        stop_services
        ;;
    --clean|--cleanup)
        cleanup_all
        ;;
    --help|-h)
        show_usage
        ;;
    *)
        echo "❌ Unknown option: ${1:-}"
        show_usage
        ;;
esac