# Rendiff Developer Documentation

Welcome to the Rendiff developer documentation. This guide is intended for developers who want to contribute to, extend, or deeply understand the Rendiff codebase.

> **About Rendiff:** Rendiff is a production-grade REST API layer built on top of [FFmpeg](https://ffmpeg.org/), providing enterprise-ready media processing capabilities.

## Documentation Index

| Document | Description |
|----------|-------------|
| [Architecture](./ARCHITECTURE.md) | System design, components, and data flow |
| [Development Setup](./DEVELOPMENT_SETUP.md) | Local environment setup and tooling |
| [Contributing Guide](./CONTRIBUTING.md) | Code standards, PR process, and guidelines |
| [API Internals](./API_INTERNALS.md) | Deep dive into API implementation |
| [Worker System](./WORKER_SYSTEM.md) | Celery workers and job processing |
| [Security Implementation](./SECURITY_IMPLEMENTATION.md) | Security architecture and practices |
| [Testing Guide](./TESTING.md) | Test strategies and running tests |
| [Database Schema](./DATABASE_SCHEMA.md) | Data models and migrations |

## Quick Links

- **Repository:** [github.com/rendiffdev/rendiff-dev](https://github.com/rendiffdev/rendiff-dev)
- **User Manual:** [../user-manual/](../user-manual/README.md)
- **API Reference:** [../user-manual/API_REFERENCE.md](../user-manual/API_REFERENCE.md)

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| API Framework | FastAPI 0.115+ | Async REST API with OpenAPI |
| Media Processing | FFmpeg 6.0+ | Video/audio encoding, transcoding |
| Task Queue | Celery 5.4+ | Distributed job processing |
| Message Broker | Redis 7.0+ / Valkey | Task queue and caching |
| Database | PostgreSQL 14+ | Primary data store |
| ORM | SQLAlchemy 2.0+ | Async database operations |
| Monitoring | Prometheus + Grafana | Metrics and dashboards |
| Reverse Proxy | Traefik 3.x | Load balancing, SSL termination |

## Getting Started as a Developer

```bash
# Clone the repository
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev

# Start development environment
./setup.sh --development

# Run tests
pytest tests/ -v

# Check code quality
black api/ worker/ tests/
flake8 api/ worker/ tests/
mypy api/ worker/
```

See [Development Setup](./DEVELOPMENT_SETUP.md) for detailed instructions.

## Project Structure

```
rendiff-dev/
├── api/                    # FastAPI application
│   ├── main.py            # Application entry point
│   ├── config.py          # Configuration management
│   ├── dependencies.py    # Dependency injection
│   ├── models/            # SQLAlchemy models
│   ├── routers/           # API route handlers
│   ├── services/          # Business logic
│   ├── middleware/        # Request/response middleware
│   └── utils/             # Utility functions
├── worker/                 # Celery worker application
│   ├── tasks.py           # Task definitions
│   ├── processors/        # Media processing logic
│   └── utils/             # Worker utilities
├── storage/                # Storage backend implementations
├── docker/                 # Docker configurations
├── config/                 # Application configs
├── tests/                  # Test suite
├── docs/                   # Documentation
│   ├── developer/         # Developer docs (you are here)
│   └── user-manual/       # End-user documentation
├── scripts/                # Utility scripts
└── monitoring/             # Prometheus/Grafana configs
```

## Support

- **Issues:** [GitHub Issues](https://github.com/rendiffdev/rendiff-dev/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rendiffdev/rendiff-dev/discussions)
