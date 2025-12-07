# Rendiff Documentation

Welcome to the Rendiff documentation. This documentation is organized into two main sections based on your needs.

> **About Rendiff:** Rendiff is a production-ready REST API for media processing, powered by [FFmpeg](https://ffmpeg.org/).

---

## Documentation Sets

### [User Manual](./user-manual/README.md)

For users who want to deploy and use Rendiff for media processing.

| Document | Description |
|----------|-------------|
| [Getting Started](./user-manual/GETTING_STARTED.md) | Quick start guide and first API call |
| [Installation](./user-manual/INSTALLATION.md) | Deployment options and setup |
| [Configuration](./user-manual/CONFIGURATION.md) | Environment variables and settings |
| [API Reference](./user-manual/API_REFERENCE.md) | Complete endpoint documentation |
| [Troubleshooting](./user-manual/TROUBLESHOOTING.md) | Common issues and solutions |

**Best for:** DevOps engineers, system administrators, application developers integrating with Rendiff.

---

### [Developer Documentation](./developer/README.md)

For developers who want to contribute to or extend Rendiff.

| Document | Description |
|----------|-------------|
| [Architecture](./developer/ARCHITECTURE.md) | System design and component overview |
| [Development Setup](./developer/DEVELOPMENT_SETUP.md) | Local development environment |
| [Contributing](./developer/CONTRIBUTING.md) | Code standards and PR process |
| [API Internals](./developer/API_INTERNALS.md) | Deep dive into API implementation |

**Best for:** Open source contributors, developers extending Rendiff.

---

## Quick Links

### For Users

```bash
# Deploy Rendiff
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev
docker compose up -d

# Test the API
curl http://localhost:8000/api/v1/health
```

### For Developers

```bash
# Set up development environment
git clone https://github.com/rendiffdev/rendiff-dev.git
cd rendiff-dev
./setup.sh --development

# Run tests
pytest tests/ -v
```

---

## Additional Resources

### Project Links

- **Repository:** [github.com/rendiffdev/rendiff-dev](https://github.com/rendiffdev/rendiff-dev)
- **Issues:** [GitHub Issues](https://github.com/rendiffdev/rendiff-dev/issues)
- **Discussions:** [GitHub Discussions](https://github.com/rendiffdev/rendiff-dev/discussions)

### External Resources

- **FFmpeg Documentation:** [ffmpeg.org/documentation.html](https://ffmpeg.org/documentation.html)
- **FFmpeg Wiki:** [trac.ffmpeg.org](https://trac.ffmpeg.org/)

---

## Documentation Standards

This documentation follows these principles:

1. **Accuracy:** All examples are tested and verified
2. **Completeness:** All features and options are documented
3. **Clarity:** Written for the target audience
4. **Maintainability:** Updated with each release

### Contributing to Documentation

Documentation improvements are welcome! See the [Contributing Guide](./developer/CONTRIBUTING.md) for details.

---

## Version

This documentation is for **Rendiff v1.0.0**.

For documentation of other versions, see the [release history](https://github.com/rendiffdev/rendiff-dev/releases).
