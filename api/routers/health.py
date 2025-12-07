"""
Health check endpoints with FastAPI 0.124+ patterns.

Provides system health monitoring without authentication requirement.
"""
from datetime import datetime
from typing import Dict, Any, Annotated

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from annotated_doc import Doc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from api.config import settings
from api.dependencies import DatabaseSession
from api.services.queue import QueueService
from api.services.storage import StorageService

logger = structlog.get_logger()

router = APIRouter()

queue_service = QueueService()
storage_service = StorageService()


# Response models for OpenAPI documentation
class HealthResponse(Dict[str, Any]):
    """Health check response schema."""
    pass


@router.get(
    "/health",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Basic health check",
    description="Quick health check endpoint for load balancers and monitoring systems.",
    response_description="Service health status",
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2025-01-15T10:30:00Z",
                        "version": "1.0.0"
                    }
                }
            }
        },
        503: {
            "description": "Service is unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2025-01-15T10:30:00Z",
                        "error": "Database connection failed"
                    }
                }
            }
        }
    },
    tags=["health"],
)
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint.

    Returns a simple health status without requiring authentication.
    Use `/health/detailed` for comprehensive component status.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
    }


@router.get(
    "/health/detailed",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Detailed health check",
    description="Comprehensive health check with status of all system components.",
    response_description="Detailed component health status",
    responses={
        200: {
            "description": "Health check completed (may include unhealthy components)",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2025-01-15T10:30:00Z",
                        "version": "1.0.0",
                        "components": {
                            "database": {"status": "healthy", "type": "postgresql"},
                            "queue": {"status": "healthy", "type": "redis"},
                            "storage": {"status": "healthy", "backends": ["local", "s3"]},
                            "ffmpeg": {"status": "healthy", "version": "ffmpeg version 6.1"}
                        }
                    }
                }
            }
        }
    },
    tags=["health"],
)
async def detailed_health_check(
    db: DatabaseSession,
) -> Dict[str, Any]:
    """
    Detailed health check with component status.

    Checks:
    - Database connectivity and response time
    - Message queue (Redis/Valkey) status
    - Storage backend availability
    - FFmpeg binary availability
    - Hardware acceleration detection
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": settings.VERSION,
        "components": {},
    }

    # Check database
    try:
        result = await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "type": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite",
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check queue
    try:
        queue_health = await queue_service.health_check()
        health_status["components"]["queue"] = queue_health
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["queue"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check storage backends
    try:
        storage_health = await storage_service.health_check()
        health_status["components"]["storage"] = storage_health
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["storage"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Check FFmpeg
    try:
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            'ffmpeg', '-version',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        if proc.returncode == 0:
            version_line = stdout.decode().split("\n")[0]
            health_status["components"]["ffmpeg"] = {
                "status": "healthy",
                "version": version_line,
            }
        else:
            raise Exception("FFmpeg not working")
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["ffmpeg"] = {
            "status": "unhealthy",
            "error": str(e),
        }

    # Return appropriate status code
    if health_status["status"] == "unhealthy":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status
        )

    return health_status


@router.get(
    "/capabilities",
    response_model=Dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Get system capabilities",
    description="Returns supported formats, codecs, operations, and hardware acceleration info.",
    response_description="System capabilities and supported features",
    responses={
        200: {
            "description": "Capabilities retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "version": "1.0.0",
                        "features": {
                            "api_version": "v1",
                            "max_file_size": 10737418240,
                            "concurrent_jobs": 10
                        },
                        "formats": {
                            "input": {"video": ["mp4", "avi", "mov"], "audio": ["mp3", "wav"]},
                            "output": {"containers": ["mp4", "webm", "hls"]}
                        },
                        "hardware_acceleration": {
                            "available": ["nvidia"],
                            "types": ["nvidia", "vaapi", "qsv"]
                        }
                    }
                }
            }
        }
    },
    tags=["health"],
)
async def get_capabilities() -> Dict[str, Any]:
    """
    Get system capabilities and supported formats.

    Returns comprehensive information about:
    - Supported input/output formats
    - Available video and audio codecs
    - Supported operations and filters
    - Quality analysis metrics
    - Hardware acceleration availability
    """
    return {
        "version": settings.VERSION,
        "features": {
            "api_version": "v1",
            "max_file_size": settings.MAX_UPLOAD_SIZE,
            "max_job_duration": settings.MAX_JOB_DURATION,
            "concurrent_jobs": settings.MAX_CONCURRENT_JOBS_PER_KEY,
        },
        "formats": {
            "input": {
                "video": [
                    "mp4", "avi", "mov", "mkv", "webm", "flv", "wmv",
                    "mpeg", "mpg", "m4v", "3gp", "3g2", "mxf", "ts", "vob"
                ],
                "audio": [
                    "mp3", "wav", "flac", "aac", "ogg", "wma", "m4a",
                    "opus", "ape", "alac", "aiff", "dts", "ac3"
                ],
            },
            "output": {
                "containers": ["mp4", "webm", "mkv", "mov", "hls", "dash"],
                "video_codecs": ["h264", "h265", "vp9", "av1", "prores"],
                "audio_codecs": ["aac", "mp3", "opus", "vorbis", "flac"],
            },
        },
        "operations": [
            "convert", "transcode", "resize", "trim", "concat",
            "watermark", "filter", "analyze", "stream"
        ],
        "filters": [
            "denoise", "deinterlace", "stabilize", "sharpen", "blur",
            "brightness", "contrast", "saturation", "hue", "eq"
        ],
        "analysis": {
            "metrics": ["vmaf", "psnr", "ssim"],
            "probing": ["format", "streams", "metadata"],
        },
        "storage_backends": list(storage_service.backends.keys()),
        "hardware_acceleration": {
            "available": await check_hardware_acceleration(),
            "types": ["nvidia", "vaapi", "qsv", "videotoolbox"],
        },
    }


async def check_hardware_acceleration() -> list:
    """Check available hardware acceleration."""
    available = []

    # Check NVIDIA
    try:
        import asyncio
        proc = await asyncio.create_subprocess_exec(
            'nvidia-smi', '--query-gpu=name', '--format=csv,noheader',
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)

        if proc.returncode == 0:
            available.append("nvidia")
    except:
        pass

    # Check VAAPI (Linux)
    import os
    if os.path.exists("/dev/dri/renderD128"):
        available.append("vaapi")

    return available
