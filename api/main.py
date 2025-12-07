"""
Rendiff - Production-Grade Media Processing API (Powered by FFmpeg)

High-performance, scalable media processing API with enterprise features.
All media processing operations are powered by FFmpeg (https://ffmpeg.org/).
"""
from contextlib import asynccontextmanager
from typing import Any, Dict

import structlog
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from api.config import settings
from api.middleware.security import SecurityHeadersMiddleware, RateLimitMiddleware
from api.models.database import init_db
from api.routers import admin, api_keys, batch, convert, health, jobs
from api.services.queue import QueueService
from api.services.storage import StorageService
from api.utils.error_handlers import (
    RendiffError,
    general_exception_handler,
    http_exception_handler,
    rendiff_exception_handler,
    validation_exception_handler,
)
from api.utils.logger import setup_logging

# Setup structured logging
setup_logging()
logger = structlog.get_logger()

# Initialize services
storage_service = StorageService()
queue_service = QueueService()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown."""
    # Startup
    logger.info("Starting Rendiff API", version=settings.VERSION)
    
    # Initialize database
    await init_db()
    
    # Initialize storage backends
    await storage_service.initialize()
    
    # Initialize queue connection
    await queue_service.initialize()
    
    # Log configuration
    logger.info(
        "Configuration loaded",
        api_host=settings.API_HOST,
        api_port=settings.API_PORT,
        workers=settings.API_WORKERS,
        storage_backends=list(storage_service.backends.keys()),
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down Rendiff API")
    await storage_service.cleanup()
    await queue_service.cleanup()


def create_application() -> FastAPI:
    """Create and configure FastAPI application with optimized settings."""
    application = FastAPI(
        title="Rendiff API",
        description="Production-grade media processing API powered by FFmpeg for professional video workflows",
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
        contact={
            "name": "Rendiff Team",
            "url": "https://rendiff.dev",
            "email": "dev@rendiff.dev",
        },
        license_info={
            "name": "MIT License",
            "url": "https://github.com/rendiffdev/rendiff-dev/blob/main/LICENSE",
        },
    )
    
    # Configure middleware stack (order matters!)
    _configure_middleware(application)
    
    # Configure exception handlers
    _configure_exception_handlers(application)
    
    # Configure routes
    _configure_routes(application)
    
    # Configure metrics endpoint
    if settings.ENABLE_METRICS:
        metrics_app = make_asgi_app()
        application.mount("/metrics", metrics_app)
    
    return application


def _configure_middleware(application: FastAPI) -> None:
    """Configure middleware stack with proper ordering."""
    # Security headers (first for all responses)
    application.add_middleware(
        SecurityHeadersMiddleware,
        csp_policy="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'",
        enable_hsts=True,
        hsts_max_age=31536000,
    )
    
    # Rate limiting (before CORS)
    application.add_middleware(
        RateLimitMiddleware,
        calls=settings.RATE_LIMIT_CALLS,
        period=settings.RATE_LIMIT_PERIOD,
        enabled=settings.ENABLE_RATE_LIMITING,
    )
    
    # CORS (last to apply to all responses)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        max_age=600,  # Cache preflight requests
    )


def _configure_exception_handlers(application: FastAPI) -> None:
    """Configure centralized exception handling."""
    application.add_exception_handler(RendiffError, rendiff_exception_handler)
    application.add_exception_handler(RequestValidationError, validation_exception_handler)
    application.add_exception_handler(HTTPException, http_exception_handler)
    application.add_exception_handler(Exception, general_exception_handler)


def _configure_routes(application: FastAPI) -> None:
    """Configure API routes with proper prefixes and tags."""
    # Core API routes
    application.include_router(health.router, prefix="/api/v1", tags=["health"])
    application.include_router(convert.router, prefix="/api/v1", tags=["processing"])
    application.include_router(jobs.router, prefix="/api/v1", tags=["jobs"])
    application.include_router(batch.router, prefix="/api/v1", tags=["batch"])
    
    # Management routes
    application.include_router(api_keys.router, prefix="/api/v1", tags=["authentication"])
    application.include_router(admin.router, prefix="/api/v1/admin", tags=["administration"])


# Create application instance
app = create_application()


@app.get("/", tags=["root"], summary="API Information")
async def root() -> Dict[str, Any]:
    """
    Get API information and capabilities.
    
    Returns basic information about the API including version, capabilities,
    and available endpoints for integration.
    """
    return {
        "name": "Rendiff API",
        "version": settings.VERSION,
        "status": "operational",
        "description": "Production-grade media processing API powered by FFmpeg",
        "endpoints": {
            "documentation": "/docs",
            "health": "/api/v1/health",
            "capabilities": "/api/v1/capabilities",
            "convert": "/api/v1/convert",
            "jobs": "/api/v1/jobs"
        },
        "features": {
            "hardware_acceleration": ["NVENC", "QSV", "VAAPI", "VCE"],
            "formats": ["MP4", "WebM", "HLS", "DASH", "MOV", "AVI"],
            "quality_metrics": ["VMAF", "PSNR", "SSIM"],
            "async_processing": True,
            "real_time_progress": True,
            "batch_operations": True
        },
        "powered_by": "FFmpeg (https://ffmpeg.org/)",
        "contact": {
            "website": "https://rendiff.dev",
            "repository": "https://github.com/rendiffdev/rendiff-dev",
            "email": "dev@rendiff.dev"
        }
    }


def main() -> None:
    """Main entry point for production server."""
    import uvicorn
    
    # Production-optimized server configuration
    uvicorn.run(
        "api.main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        workers=1 if settings.DEBUG else settings.API_WORKERS,
        reload=settings.API_RELOAD,
        log_config=None,  # Use structured logging
        access_log=False,  # Handled by middleware
        server_header=False,  # Security
        date_header=False,  # Security
    )


if __name__ == "__main__":
    main()