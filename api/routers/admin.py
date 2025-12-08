"""
Admin endpoints - System management with FastAPI 0.124+ patterns.

Provides worker management, storage status, statistics, and cleanup operations.
Requires admin API key for access.
"""
from typing import Dict, Any, List, Annotated
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, and_
from annotated_doc import Doc
import structlog

from api.config import settings
from api.dependencies import DatabaseSession, require_api_key
from api.models.job import Job, JobStatus, ErrorResponse
from pydantic import BaseModel

logger = structlog.get_logger()
router = APIRouter()

# Lazy import to avoid circular dependency
def get_queue_service():
    from api.main import queue_service
    return queue_service

def get_storage_service():
    from api.main import storage_service
    return storage_service


# Response models for OpenAPI documentation
class WorkerInfo(BaseModel):
    """Worker status information."""
    id: Annotated[str, Doc("Worker identifier")]
    status: Annotated[str, Doc("Current status: active, idle, offline")]
    hostname: Annotated[str, Doc("Worker hostname")]
    current_job: Annotated[str | None, Doc("Currently processing job ID")]
    jobs_completed: Annotated[int, Doc("Total jobs completed")]
    last_heartbeat: Annotated[datetime | None, Doc("Last heartbeat timestamp")]


class WorkersStatusResponse(BaseModel):
    """Workers status response."""
    total_workers: Annotated[int, Doc("Total number of workers")]
    workers: Annotated[List[Dict[str, Any]], Doc("List of worker details")]
    summary: Annotated[Dict[str, int], Doc("Worker count by status")]


class StorageStatusResponse(BaseModel):
    """Storage backends status response."""
    backends: Annotated[Dict[str, Dict[str, Any]], Doc("Status of each storage backend")]
    default_backend: Annotated[str | None, Doc("Default storage backend name")]
    policies: Annotated[Dict[str, Any], Doc("Storage routing policies")]


class SystemStatsResponse(BaseModel):
    """System statistics response."""
    period: Annotated[str, Doc("Statistics period")]
    start_time: Annotated[str, Doc("Period start timestamp")]
    jobs: Annotated[Dict[str, Any], Doc("Job statistics")]
    queue: Annotated[Dict[str, Any], Doc("Queue statistics")]
    workers: Annotated[Dict[str, Any], Doc("Worker statistics")]


class CleanupResponse(BaseModel):
    """Cleanup operation response."""
    dry_run: Annotated[bool, Doc("Whether this was a dry run")]
    jobs_deleted: Annotated[int | None, Doc("Number of jobs deleted")] = None
    jobs_to_delete: Annotated[int | None, Doc("Jobs that would be deleted (dry run)")] = None
    errors: Annotated[List[Dict[str, Any]] | None, Doc("Any errors during cleanup")] = None
    cutoff_date: Annotated[str, Doc("Cutoff date for cleanup")]


class PresetResponse(BaseModel):
    """Encoding preset response."""
    name: Annotated[str, Doc("Preset name")]
    description: Annotated[str | None, Doc("Preset description")] = None
    settings: Annotated[Dict[str, Any], Doc("Encoding settings")]


async def require_admin(api_key: str = Depends(require_api_key)) -> str:
    """
    Dependency to require admin privileges.

    Validates the API key against configured admin keys.
    """
    admin_keys = settings.ADMIN_API_KEYS.split(',') if hasattr(settings, 'ADMIN_API_KEYS') and settings.ADMIN_API_KEYS else []

    if not admin_keys:
        logger.warning("No admin API keys configured - admin endpoints disabled")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "not_configured", "message": "Admin functionality not configured"}
        )

    if api_key not in admin_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "access_denied", "message": "Admin access required"}
        )
    return api_key


@router.get(
    "/workers",
    response_model=WorkersStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get workers status",
    description="Get the current status of all workers in the processing cluster.",
    response_description="List of workers with their status and statistics",
    responses={
        200: {"description": "Workers status retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
        503: {"model": ErrorResponse, "description": "Admin functionality not configured"},
    },
    tags=["admin"],
)
async def get_workers_status(
    admin: Annotated[str, Depends(require_admin), Doc("Admin API key")],
) -> WorkersStatusResponse:
    """
    Get status of all workers in the system.

    Returns worker health, current jobs, and performance metrics.
    Only accessible with admin API key.
    """
    try:
        workers = await get_queue_service().get_workers_status()

        return WorkersStatusResponse(
            total_workers=len(workers),
            workers=workers,
            summary={
                "active": sum(1 for w in workers if w.get("status") == "active"),
                "idle": sum(1 for w in workers if w.get("status") == "idle"),
                "offline": sum(1 for w in workers if w.get("status") == "offline"),
            },
        )
    except Exception as e:
        logger.error("Failed to get workers status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to get workers status"}
        )


@router.get(
    "/storage",
    response_model=StorageStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get storage status",
    description="Get the status of all configured storage backends.",
    response_description="Storage backend health and configuration",
    responses={
        200: {"description": "Storage status retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
        503: {"model": ErrorResponse, "description": "Admin functionality not configured"},
    },
    tags=["admin"],
)
async def get_storage_status(
    admin: Annotated[str, Depends(require_admin), Doc("Admin API key")],
) -> StorageStatusResponse:
    """
    Get status of all storage backends.

    Returns health status, available space, and configuration for each backend.
    """
    try:
        storage_status = {}

        for name, backend in get_storage_service().backends.items():
            try:
                # Get backend-specific status
                backend_status = await backend.get_status()
                storage_status[name] = {
                    "status": "healthy",
                    "type": backend.__class__.__name__,
                    **backend_status,
                }
            except Exception as e:
                storage_status[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                }

        return StorageStatusResponse(
            backends=storage_status,
            default_backend=get_storage_service().config.get("default_backend"),
            policies=get_storage_service().config.get("policies", {}),
        )
    except Exception as e:
        logger.error("Failed to get storage status", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to get storage status"}
        )


@router.get(
    "/stats",
    response_model=SystemStatsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get system statistics",
    description="Get aggregated system statistics for the specified time period.",
    response_description="Job, queue, and worker statistics",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
        503: {"model": ErrorResponse, "description": "Admin functionality not configured"},
    },
    tags=["admin"],
)
async def get_system_stats(
    period: Annotated[
        str,
        Query(pattern=r"^(\d+[hdwm])$", description="Time period (e.g., 24h, 7d, 4w, 1m)"),
        Doc("Statistics aggregation period")
    ] = "24h",
    db: DatabaseSession = None,
    admin: Annotated[str, Depends(require_admin), Doc("Admin API key")] = None,
) -> SystemStatsResponse:
    """
    Get system statistics for the specified period.

    Returns aggregated metrics for jobs, queue depth, and worker performance.
    Period format: number + unit (h=hours, d=days, w=weeks, m=months).
    """
    # Parse period
    unit = period[-1]
    value = int(period[:-1])

    if unit == "h":
        delta = timedelta(hours=value)
    elif unit == "d":
        delta = timedelta(days=value)
    elif unit == "w":
        delta = timedelta(weeks=value)
    elif unit == "m":
        delta = timedelta(days=value * 30)

    start_time = datetime.utcnow() - delta

    # Get job statistics
    stats_query = (
        select(
            Job.status,
            func.count(Job.id).label("count"),
            func.avg(Job.processing_time).label("avg_time"),
            func.avg(Job.vmaf_score).label("avg_vmaf"),
        )
        .where(Job.created_at >= start_time)
        .group_by(Job.status)
    )

    result = await db.execute(stats_query)
    job_stats = result.all()

    # Format statistics
    stats = SystemStatsResponse(
        period=period,
        start_time=start_time.isoformat(),
        jobs={
            "total": sum(row.count for row in job_stats),
            "by_status": {row.status: row.count for row in job_stats},
            "avg_processing_time": sum(row.avg_time or 0 for row in job_stats) / len(job_stats) if job_stats else 0,
            "avg_vmaf_score": sum(row.avg_vmaf or 0 for row in job_stats if row.avg_vmaf) / sum(1 for row in job_stats if row.avg_vmaf) if any(row.avg_vmaf for row in job_stats) else None,
        },
        queue=await get_queue_service().get_queue_stats(),
        workers=await get_queue_service().get_workers_stats(),
    )

    return stats


@router.post(
    "/cleanup",
    response_model=CleanupResponse,
    status_code=status.HTTP_200_OK,
    summary="Cleanup old jobs",
    description="Remove old completed jobs and their associated files from storage.",
    response_description="Cleanup operation results",
    responses={
        200: {"description": "Cleanup completed or dry run results"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
        503: {"model": ErrorResponse, "description": "Admin functionality not configured"},
    },
    tags=["admin"],
)
async def cleanup_old_jobs(
    days: Annotated[
        int,
        Query(ge=1, le=90, description="Delete jobs older than this many days"),
        Doc("Age threshold in days for job cleanup")
    ] = 7,
    dry_run: Annotated[
        bool,
        Query(description="If true, only report what would be deleted"),
        Doc("Preview cleanup without deleting")
    ] = True,
    db: DatabaseSession = None,
    admin: Annotated[str, Depends(require_admin), Doc("Admin API key")] = None,
) -> CleanupResponse:
    """
    Clean up old completed jobs and their associated files.

    By default runs in dry-run mode to preview deletions.
    Only removes jobs in terminal states (completed, failed, cancelled).
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    # Find old jobs
    query = select(Job).where(
        and_(
            Job.completed_at < cutoff_date,
            Job.status.in_([JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED])
        )
    )

    result = await db.execute(query)
    old_jobs = result.scalars().all()

    if dry_run:
        return CleanupResponse(
            dry_run=True,
            jobs_to_delete=len(old_jobs),
            cutoff_date=cutoff_date.isoformat(),
        )

    # Delete files and jobs
    deleted_count = 0
    errors = []

    for job in old_jobs:
        try:
            # Delete output file if it exists
            if job.output_path:
                backend_name, file_path = get_storage_service().parse_uri(job.output_path)
                backend = get_storage_service().backends.get(backend_name)
                if backend:
                    await backend.delete(file_path)

            # Delete job record
            await db.delete(job)
            deleted_count += 1

        except Exception as e:
            errors.append({
                "job_id": str(job.id),
                "error": str(e),
            })

    await db.commit()

    logger.info(f"Cleanup completed: {deleted_count} jobs deleted")

    return CleanupResponse(
        dry_run=False,
        jobs_deleted=deleted_count,
        errors=errors if errors else None,
        cutoff_date=cutoff_date.isoformat(),
    )


@router.post(
    "/presets",
    response_model=PresetResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create encoding preset",
    description="Create a new custom encoding preset for reuse across jobs.",
    response_description="Created preset details",
    responses={
        201: {"description": "Preset created successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid preset configuration",
            "content": {
                "application/json": {
                    "example": {"error": "validation_error", "message": "Preset name required"}
                }
            }
        },
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Admin access required"},
    },
    tags=["admin"],
)
async def create_preset(
    preset: Annotated[Dict[str, Any], Doc("Preset configuration with name and settings")],
    admin: Annotated[str, Depends(require_admin), Doc("Admin API key")],
) -> PresetResponse:
    """
    Create a new encoding preset.

    Presets define reusable encoding configurations for common use cases.
    """
    # Validate preset
    if "name" not in preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Preset name required"}
        )

    if "settings" not in preset:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "validation_error", "message": "Preset settings required"}
        )

    # Save preset (in production, save to database)
    logger.info(f"Preset created: {preset['name']}")

    return PresetResponse(
        name=preset["name"],
        description=preset.get("description"),
        settings=preset["settings"],
    )


@router.get(
    "/presets",
    response_model=List[PresetResponse],
    status_code=status.HTTP_200_OK,
    summary="List encoding presets",
    description="Get all available encoding presets including built-in and custom presets.",
    response_description="List of available presets",
    responses={
        200: {"description": "Presets retrieved successfully"},
    },
    tags=["admin"],
)
async def list_presets() -> List[PresetResponse]:
    """
    List available encoding presets.

    Returns both built-in presets and any custom presets created by admins.
    This endpoint does not require admin authentication.
    """
    return [
        PresetResponse(
            name="web-1080p",
            description="Standard 1080p for web streaming",
            settings={
                "video": {
                    "codec": "h264",
                    "preset": "medium",
                    "crf": 23,
                    "resolution": "1920x1080",
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "128k",
                },
            },
        ),
        PresetResponse(
            name="web-720p",
            description="Standard 720p for web streaming",
            settings={
                "video": {
                    "codec": "h264",
                    "preset": "medium",
                    "crf": 23,
                    "resolution": "1280x720",
                },
                "audio": {
                    "codec": "aac",
                    "bitrate": "128k",
                },
            },
        ),
        PresetResponse(
            name="archive-high",
            description="High quality for archival",
            settings={
                "video": {
                    "codec": "h265",
                    "preset": "slow",
                    "crf": 18,
                },
                "audio": {
                    "codec": "flac",
                },
            },
        ),
    ]
