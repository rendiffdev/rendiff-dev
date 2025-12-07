# Contributing to Rendiff

We welcome contributions to Rendiff! This guide will help you get started.

> **Note:** Rendiff is a REST API layer powered by FFmpeg. All media processing is handled by FFmpeg under the hood.

## Code of Conduct

Please note that this project is released with a Contributor Code of Conduct. By participating in this project you agree to abide by its terms.

## How to Contribute

### Reporting Issues

- Check if the issue already exists
- Include steps to reproduce
- Provide system information
- Include relevant logs

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Write/update tests as needed
5. Ensure all tests pass (`pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to your branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/rendiff-dev.git
cd rendiff-dev

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run linting
black api/ worker/ tests/
flake8 api/ worker/ tests/
```

## Coding Standards

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Write docstrings for all functions and classes
- Keep functions focused and small
- Add unit tests for new functionality

## Testing

- Write tests for all new features
- Maintain or improve code coverage
- Run the full test suite before submitting PR
- Include integration tests for API endpoints

## Documentation

- Update README.md if needed
- Document new API endpoints
- Update configuration examples
- Add docstrings to new code

## Commit Messages

Follow conventional commit format:

```
type(scope): subject

body (optional)

footer (optional)
```

Types: feat, fix, docs, style, refactor, test, chore

Example:
```
feat(api): add batch processing endpoint

Implements batch processing for multiple video files
with progress tracking and error handling

Closes #123
```

## Questions?

Feel free to open an issue for any questions about contributing.

Thank you for contributing to Rendiff!