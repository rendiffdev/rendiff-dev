# Contributing to Rendiff

Thank you for your interest in contributing to Rendiff! This guide covers everything you need to know to contribute effectively.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for all contributors.

## How to Contribute

### Reporting Issues

Before creating an issue:

1. **Search existing issues** to avoid duplicates
2. **Use the issue templates** when available
3. **Provide complete information:**
   - Rendiff version
   - Operating system
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs or screenshots

### Feature Requests

We welcome feature suggestions! When proposing new features:

1. Explain the use case clearly
2. Describe the expected behavior
3. Consider backward compatibility
4. Be open to discussion and alternatives

### Pull Requests

#### Before Starting

1. Check for existing PRs addressing the same issue
2. For significant changes, open an issue first to discuss
3. Ensure you can sign off your commits (DCO)

#### Development Workflow

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/rendiff-dev.git
cd rendiff-dev

# 3. Add upstream remote
git remote add upstream https://github.com/rendiffdev/rendiff-dev.git

# 4. Create a feature branch
git checkout -b feature/your-feature-name

# 5. Make your changes
# ... edit files ...

# 6. Run tests and quality checks
pytest tests/ -v
black api/ worker/ tests/
flake8 api/ worker/ tests/
mypy api/ worker/

# 7. Commit your changes
git add .
git commit -m "feat(api): add new endpoint for batch processing"

# 8. Push to your fork
git push origin feature/your-feature-name

# 9. Create Pull Request on GitHub
```

#### PR Requirements

- [ ] All tests pass
- [ ] Code follows project style guidelines
- [ ] New code has appropriate test coverage
- [ ] Documentation updated if needed
- [ ] Commit messages follow conventions
- [ ] PR description explains changes clearly

## Coding Standards

### Python Style Guide

We follow PEP 8 with some project-specific conventions:

```python
# Good: Clear, descriptive names
async def create_conversion_job(
    input_path: str,
    output_path: str,
    options: ConversionOptions,
) -> Job:
    """
    Create a new media conversion job.

    Args:
        input_path: Source file path (storage URI format)
        output_path: Destination file path
        options: Conversion parameters

    Returns:
        Created Job instance

    Raises:
        ValidationError: If paths are invalid
        StorageError: If storage backend unavailable
    """
    # Implementation...

# Bad: Unclear names, no type hints
async def create(p1, p2, opts):
    # No docstring...
```

### Type Hints

Always use type hints for function signatures:

```python
from typing import List, Optional, Dict, Any

def process_operations(
    operations: List[Dict[str, Any]],
    options: Optional[ProcessingOptions] = None,
) -> ProcessingResult:
    ...
```

### Async/Await

Use async functions for I/O operations:

```python
# Good: Async for I/O
async def fetch_job(job_id: str) -> Optional[Job]:
    async with get_session() as session:
        return await session.get(Job, job_id)

# Bad: Blocking I/O in async context
async def fetch_job_bad(job_id: str) -> Optional[Job]:
    with get_sync_session() as session:  # Blocks!
        return session.get(Job, job_id)
```

### Error Handling

Use specific exceptions and proper error messages:

```python
from api.utils.error_handlers import ValidationError, StorageError

# Good: Specific exception with context
if not input_path.startswith(('local://', 's3://')):
    raise ValidationError(
        f"Invalid storage URI format: {input_path}",
        field="input_path"
    )

# Bad: Generic exception
if not valid:
    raise Exception("error")
```

### Imports

Organize imports in this order:

```python
# 1. Standard library
import os
from pathlib import Path
from typing import List, Optional

# 2. Third-party packages
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

# 3. Local imports
from api.config import settings
from api.models.job import Job
from api.services.storage import StorageService
```

## Commit Message Conventions

Follow the Conventional Commits specification:

```
type(scope): subject

body (optional)

footer (optional)
```

### Types

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Code style (formatting, semicolons) |
| `refactor` | Code change that neither fixes nor adds |
| `perf` | Performance improvement |
| `test` | Adding or updating tests |
| `chore` | Build process, dependencies |
| `ci` | CI/CD configuration |

### Scopes

| Scope | Description |
|-------|-------------|
| `api` | API layer changes |
| `worker` | Worker/task changes |
| `storage` | Storage backend changes |
| `db` | Database/models changes |
| `config` | Configuration changes |
| `docker` | Docker/deployment changes |
| `deps` | Dependency updates |

### Examples

```bash
# Feature
git commit -m "feat(api): add batch processing endpoint"

# Bug fix
git commit -m "fix(worker): handle timeout in FFmpeg processing"

# Documentation
git commit -m "docs(api): update authentication examples"

# Breaking change
git commit -m "feat(api)!: change job status enum values

BREAKING CHANGE: Job status 'in_progress' renamed to 'processing'"
```

## Testing Guidelines

### Test Structure

```
tests/
├── conftest.py          # Shared fixtures
├── test_health.py       # Health check tests
├── test_jobs.py         # Job endpoint tests
├── test_models.py       # Model unit tests
├── test_services.py     # Service layer tests
├── test_integration.py  # Integration tests
├── test_security.py     # Security tests
└── test_performance.py  # Performance tests
```

### Writing Tests

```python
import pytest
from fastapi.testclient import TestClient

class TestJobEndpoints:
    """Tests for job management endpoints."""

    def test_create_job_success(self, client: TestClient, auth_headers: dict):
        """Test successful job creation."""
        response = client.post(
            "/api/v1/convert",
            json={
                "input_path": "local:///storage/test.mp4",
                "output_path": "local:///storage/output.mp4",
            },
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "pending"

    def test_create_job_invalid_path(self, client: TestClient, auth_headers: dict):
        """Test job creation with invalid path."""
        response = client.post(
            "/api/v1/convert",
            json={
                "input_path": "../../../etc/passwd",  # Path traversal attempt
                "output_path": "local:///storage/output.mp4",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "traversal" in response.json()["detail"].lower()
```

### Test Coverage

- Aim for >80% code coverage
- All new features must have tests
- Bug fixes should include regression tests

```bash
# Run with coverage
pytest tests/ --cov=api --cov=worker --cov-report=html

# View report
open htmlcov/index.html
```

## Documentation Guidelines

### Code Documentation

Every public function needs a docstring:

```python
async def transcode_video(
    input_path: str,
    output_path: str,
    codec: str = "h264",
    preset: str = "medium",
) -> TranscodeResult:
    """
    Transcode video file using FFmpeg.

    This function handles the transcoding of video files to different
    codecs and formats. It supports hardware acceleration when available.

    Args:
        input_path: Source video file path (storage URI)
        output_path: Destination file path
        codec: Video codec (h264, h265, vp9, av1). Default: h264
        preset: Encoding preset (ultrafast to veryslow). Default: medium

    Returns:
        TranscodeResult with output path and processing metrics

    Raises:
        ValidationError: If codec is not supported
        ProcessingError: If FFmpeg fails
        StorageError: If file operations fail

    Example:
        >>> result = await transcode_video(
        ...     "local:///input.mp4",
        ...     "local:///output.webm",
        ...     codec="vp9"
        ... )
        >>> print(result.output_path)
        local:///output.webm
    """
```

### API Documentation

Update OpenAPI documentation for endpoint changes:

```python
@router.post(
    "/convert",
    response_model=JobResponse,
    status_code=201,
    summary="Create conversion job",
    description="""
    Create a new media conversion job.

    The job will be queued for processing by a worker. Use the returned
    job ID to track progress via the `/jobs/{id}` endpoint.

    **Supported formats:**
    - Video: MP4, WebM, MKV, AVI, MOV
    - Audio: MP3, AAC, FLAC, WAV

    **Rate limits:** 200 requests/hour per API key
    """,
    responses={
        201: {"description": "Job created successfully"},
        400: {"description": "Invalid request parameters"},
        401: {"description": "Missing or invalid API key"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def create_conversion_job(...):
    ...
```

## Security Guidelines

### Reporting Security Issues

**Do not** create public GitHub issues for security vulnerabilities.

Instead, report security issues to: security@rendiff.dev

### Security Best Practices

1. **Input Validation:** Always validate and sanitize user input
2. **Path Security:** Use the validators module for file paths
3. **SQL Injection:** Use SQLAlchemy ORM, never raw SQL with user input
4. **Secrets:** Never commit secrets, use environment variables
5. **Dependencies:** Keep dependencies updated, run security scans

```python
# Good: Use validators
from api.utils.validators import validate_secure_path

path = validate_secure_path(user_input)

# Bad: Direct path usage
path = user_input  # Dangerous!
```

## Review Process

### What Reviewers Look For

1. **Correctness:** Does the code work as intended?
2. **Security:** Are there any security concerns?
3. **Performance:** Any obvious performance issues?
4. **Maintainability:** Is the code readable and maintainable?
5. **Testing:** Are there adequate tests?
6. **Documentation:** Is documentation updated?

### Addressing Review Feedback

- Respond to all comments
- Push fixes as new commits (easier to review)
- Request re-review when ready
- Squash commits before merge if requested

## Getting Help

- **Questions:** Open a GitHub Discussion
- **Bugs:** Create a GitHub Issue
- **Security:** Email security@rendiff.dev
- **Chat:** Join our Discord server

## Recognition

Contributors are recognized in:
- CONTRIBUTORS.md file
- Release notes
- Project documentation

Thank you for contributing to Rendiff!
