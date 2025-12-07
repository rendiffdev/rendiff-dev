# Development Setup Guide

This guide walks you through setting up a local development environment for Rendiff.

## Prerequisites

### Required Software

| Software | Minimum Version | Purpose |
|----------|----------------|---------|
| Docker | 20.10+ | Container runtime |
| Docker Compose | 2.0+ | Multi-container orchestration |
| Python | 3.12+ | API and worker runtime |
| Git | 2.30+ | Version control |

### Optional (for local development without Docker)

| Software | Version | Purpose |
|----------|---------|---------|
| FFmpeg | 6.0+ | Media processing |
| PostgreSQL | 14+ | Database |
| Redis | 7.0+ | Queue and cache |

### Hardware Recommendations

| Environment | CPU | RAM | Storage |
|-------------|-----|-----|---------|
| Development | 4 cores | 8GB | 50GB SSD |
| Testing | 8 cores | 16GB | 100GB SSD |

## Quick Start (Docker)

The fastest way to get started:

```bash
# Clone the repository
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Start development environment
./setup.sh --development

# Verify it's running
curl http://localhost:8000/api/v1/health
```

The development setup includes:
- SQLite database (no PostgreSQL needed)
- Redis for job queue
- Hot-reload enabled
- Debug mode active
- No authentication required

## Manual Setup

### 1. Clone and Configure

```bash
# Clone repository
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Create Python virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` for development:

```bash
# Development settings
DEBUG=true
TESTING=false

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_LOG_LEVEL=debug
API_WORKERS=1

# Database (SQLite for simplicity)
DATABASE_URL=sqlite+aiosqlite:///data/rendiff.db

# Redis (if running locally)
REDIS_URL=redis://localhost:6379/0

# Disable authentication for development
ENABLE_API_KEYS=false

# Storage
STORAGE_PATH=./storage
TEMP_PATH=/tmp/rendiff
```

### 3. Start Dependencies

Using Docker (recommended):

```bash
# Start only Redis
docker run -d --name rendiff-redis -p 6379:6379 redis:7.2-alpine
```

Or install locally:

```bash
# macOS
brew install redis
brew services start redis

# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
```

### 4. Initialize Database

```bash
# Create data directory
mkdir -p data

# Run migrations
alembic upgrade head
```

### 5. Start the API

```bash
# Development mode with hot reload
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Start a Worker (Optional)

In a separate terminal:

```bash
source venv/bin/activate
celery -A worker.celery_app worker --loglevel=info
```

## Docker Development Environment

### Full Stack Development

```bash
# Start all services with development overrides
docker compose -f compose.yml -f compose.override.yml up -d

# View logs
docker compose logs -f api

# Rebuild after code changes
docker compose build api
docker compose up -d api
```

### Service-Specific Commands

```bash
# Start only specific services
docker compose up -d postgres redis

# Run API locally while using Docker services
export DATABASE_URL=postgresql://rendiff_user:defaultpassword@localhost:5432/rendiff
export REDIS_URL=redis://localhost:6379/0
uvicorn api.main:app --reload
```

## IDE Configuration

### VS Code

Recommended extensions:
- Python (Microsoft)
- Pylance
- Docker
- GitLens
- REST Client

`.vscode/settings.json`:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/venv/bin/python",
  "python.linting.enabled": true,
  "python.linting.flake8Enabled": true,
  "python.formatting.provider": "black",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["tests/"],
  "editor.formatOnSave": true,
  "editor.codeActionsOnSave": {
    "source.organizeImports": true
  }
}
```

### PyCharm

1. Set Python interpreter to `venv/bin/python`
2. Mark `api/` and `worker/` as Sources Root
3. Configure pytest as test runner
4. Enable Black formatter

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=api --cov=worker --cov-report=html

# Run specific test file
pytest tests/test_jobs.py -v

# Run tests matching pattern
pytest tests/ -k "test_convert" -v

# Run only fast tests (no integration)
pytest tests/ -m "not integration" -v
```

## Code Quality Tools

### Formatting

```bash
# Format code with Black
black api/ worker/ tests/

# Check without modifying
black api/ worker/ tests/ --check
```

### Linting

```bash
# Run flake8
flake8 api/ worker/ tests/

# Run with specific config
flake8 --config=.flake8
```

### Type Checking

```bash
# Run mypy
mypy api/ worker/

# Strict mode
mypy api/ worker/ --strict
```

### Import Sorting

```bash
# Sort imports
isort api/ worker/ tests/

# Check without modifying
isort api/ worker/ tests/ --check
```

### Pre-commit Hooks

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

## Database Management

### Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Add new column"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history

# View current revision
alembic current
```

### Database Shell

```bash
# SQLite
sqlite3 data/rendiff.db

# PostgreSQL (Docker)
docker compose exec postgres psql -U rendiff_user -d rendiff
```

## Debugging

### API Debugging

```python
# Add to code for breakpoints
import pdb; pdb.set_trace()

# Or use debugpy for VS Code
import debugpy
debugpy.listen(5678)
debugpy.wait_for_client()
```

### Worker Debugging

```bash
# Run worker with verbose logging
celery -A worker.celery_app worker --loglevel=debug

# Run single task synchronously
python -c "from worker.tasks import process_job; process_job('job-id')"
```

### Request Debugging

```bash
# View all requests in real-time
docker compose logs -f api | grep -E "(GET|POST|PUT|DELETE)"

# Test endpoint with curl
curl -X POST http://localhost:8000/api/v1/convert \
  -H "Content-Type: application/json" \
  -d '{"input_path": "local:///storage/test.mp4", "output_path": "local:///storage/out.mp4"}'
```

## Common Development Tasks

### Adding a New Endpoint

1. Create router in `api/routers/`
2. Add route handler functions
3. Register router in `api/main.py`
4. Add tests in `tests/`
5. Update API documentation

### Adding a New Model

1. Create model in `api/models/`
2. Create Alembic migration
3. Add repository/service methods
4. Add tests

### Adding a New Worker Task

1. Define task in `worker/tasks.py`
2. Implement processor in `worker/processors/`
3. Add task tests
4. Update documentation

## Troubleshooting Development Issues

### Port Already in Use

```bash
# Find process using port
lsof -i :8000

# Kill process
kill -9 <PID>
```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker compose ps postgres

# View PostgreSQL logs
docker compose logs postgres

# Reset database
docker compose down -v
docker compose up -d postgres
alembic upgrade head
```

### Redis Connection Issues

```bash
# Test Redis connection
redis-cli ping

# Check Redis logs
docker compose logs redis
```

### FFmpeg Not Found

```bash
# Check FFmpeg installation
ffmpeg -version

# Install on macOS
brew install ffmpeg

# Install on Ubuntu
sudo apt install ffmpeg
```

## Next Steps

- Read the [Architecture Guide](./ARCHITECTURE.md)
- Review the [Contributing Guide](./CONTRIBUTING.md)
- Explore [API Internals](./API_INTERNALS.md)
