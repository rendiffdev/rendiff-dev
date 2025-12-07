"""
Jobs endpoint - Job management and monitoring with FastAPI 0.124+ patterns.

Provides job listing, status, cancellation, and real-time progress streaming.
"""
from typing import Optional, Annotated
from uuid import UUID
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from annotated_doc import Doc
from sqlalchemy import select, func
import structlog

from api.config import settings
from api.dependencies import DatabaseSession, RequiredAPIKey
from api.models.job import Job, JobStatus, JobResponse, JobListResponse, JobProgress, ErrorResponse
from api.services.queue import QueueService

logger = structlog.get_logger()

router = APIRouter()

queue_service = QueueService()


@router.get(
    "/jobs",
    response_model=JobListResponse,
    status_code=status.HTTP_200_OK,
    summary="List jobs",
    description="List all jobs for the authenticated API key with filtering and pagination.",
    response_description="Paginated list of jobs",
    responses={
        200: {"description": "Jobs retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
    },
    tags=["jobs"],
)
async def list_jobs(
    status_filter: Annotated[
        Optional[JobStatus],
        Query(alias="status", description="Filter by job status"),
        Doc("Filter jobs by their current status")
    ] = None,
    page: Annotated[
        int,
        Query(ge=1, description="Page number (1-indexed)"),
        Doc("Page number for pagination")
    ] = 1,
    per_page: Annotated[
        int,
        Query(ge=1, le=100, description="Items per page (max 100)"),
        Doc("Number of items per page")
    ] = 20,
    sort: Annotated[
        str,
        Query(
            description="Sort field and order (e.g., 'created_at:desc')",
            pattern=r"^[a-z_]+:(asc|desc)$"
        ),
        Doc("Sort specification: field:order")
    ] = "created_at:desc",
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> JobListResponse:
    """
    List jobs with optional filtering and pagination.

    Supports filtering by status and sorting by any field.
    Only returns jobs owned by the authenticated API key.
    """
    # Parse sort parameter
    sort_field, sort_order = sort.split(":") if ":" in sort else (sort, "asc")

    # Build query
    query = select(Job).where(Job.api_key == api_key)

    if status_filter:
        query = query.where(Job.status == status_filter)

    # Apply sorting
    order_column = getattr(Job, sort_field, Job.created_at)
    if sort_order == "desc":
        query = query.order_by(order_column.desc())
    else:
        query = query.order_by(order_column.asc())

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Apply pagination
    offset = (page - 1) * per_page
    query = query.offset(offset).limit(per_page)

    # Execute query
    result = await db.execute(query)
    jobs = result.scalars().all()

    # Convert to response models
    job_responses = []
    for job in jobs:
        job_response = JobResponse(
            id=job.id,
            status=job.status,
            priority=job.priority,
            progress=job.progress,
            stage=job.stage,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            eta_seconds=job.eta_seconds,
            links={
                "self": f"/api/v1/jobs/{job.id}",
                "events": f"/api/v1/jobs/{job.id}/events",
                "logs": f"/api/v1/jobs/{job.id}/logs",
            },
        )

        if job.status == JobStatus.FAILED:
            job_response.error = {
                "message": job.error_message,
                "details": job.error_details,
            }

        job_responses.append(job_response)

    return JobListResponse(
        jobs=job_responses,
        total=total,
        page=page,
        per_page=per_page,
        has_next=total > page * per_page,
        has_prev=page > 1,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobResponse,
    status_code=status.HTTP_200_OK,
    summary="Get job details",
    description="Get detailed information about a specific job including progress and quality metrics.",
    response_description="Job details",
    responses={
        200: {"description": "Job found"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to this job"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
    tags=["jobs"],
)
async def get_job(
    job_id: Annotated[UUID, Doc("Unique job identifier")],
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> JobResponse:
    """
    Get detailed information about a specific job.

    Returns full job details including:
    - Current status and progress
    - Quality metrics (VMAF, PSNR, SSIM) if available
    - Error details if failed
    - HATEOAS links for related resources
    """
    # Get job from database
    job = await db.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Job not found"}
        )

    # Check ownership
    if job.api_key != api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "access_denied", "message": "Access denied"}
        )

    # Build response
    response = JobResponse(
        id=job.id,
        status=job.status,
        priority=job.priority,
        progress=job.progress,
        stage=job.stage,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        eta_seconds=job.eta_seconds,
        links={
            "self": f"/api/v1/jobs/{job.id}",
            "events": f"/api/v1/jobs/{job.id}/events",
            "logs": f"/api/v1/jobs/{job.id}/logs",
            "cancel": f"/api/v1/jobs/{job.id}" if job.status in [JobStatus.QUEUED, JobStatus.PROCESSING] else None,
        },
    )

    # Add progress details
    if job.status == JobStatus.PROCESSING:
        response.progress_details = {
            "percentage": job.progress,
            "stage": job.stage,
            "fps": job.fps,
            "eta_seconds": job.eta_seconds,
        }

    # Add error details if failed
    if job.status == JobStatus.FAILED:
        response.error = {
            "message": job.error_message,
            "details": job.error_details,
            "retry_count": job.retry_count,
        }

    # Add quality metrics if available
    if job.vmaf_score or job.psnr_score or job.ssim_score:
        response.progress_details = response.progress_details or {}
        response.progress_details["quality"] = {}
        if job.vmaf_score:
            response.progress_details["quality"]["vmaf"] = job.vmaf_score
        if job.psnr_score:
            response.progress_details["quality"]["psnr"] = job.psnr_score
        if job.ssim_score:
            response.progress_details["quality"]["ssim"] = job.ssim_score

    return response


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_200_OK,
    summary="Cancel job",
    description="Cancel a queued or processing job.",
    response_description="Cancellation result",
    responses={
        200: {"description": "Job cancelled successfully"},
        400: {"model": ErrorResponse, "description": "Job cannot be cancelled (already completed)"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to this job"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
    tags=["jobs"],
)
async def cancel_job(
    job_id: Annotated[UUID, Doc("Unique job identifier to cancel")],
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> dict:
    """
    Cancel a queued or processing job.

    Only jobs with status 'queued' or 'processing' can be cancelled.
    Completed, failed, or already cancelled jobs cannot be cancelled.
    """
    # Get job
    job = await db.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Job not found"}
        )

    # Check ownership
    if job.api_key != api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "access_denied", "message": "Access denied"}
        )

    # Check if job can be cancelled
    if job.status not in [JobStatus.QUEUED, JobStatus.PROCESSING]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_state",
                "message": f"Cannot cancel job with status: {job.status}"
            }
        )

    # Cancel in queue
    if job.status == JobStatus.QUEUED:
        await queue_service.cancel_job(str(job_id))
    elif job.status == JobStatus.PROCESSING:
        # Send cancel signal to worker
        await queue_service.cancel_running_job(str(job_id), job.worker_id)

    # Update job status
    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.utcnow()
    await db.commit()

    logger.info("Job cancelled", job_id=str(job_id))

    return {
        "id": str(job_id),
        "status": "cancelled",
        "message": "Job has been cancelled"
    }


@router.get(
    "/jobs/{job_id}/events",
    summary="Stream job progress",
    description="Stream real-time job progress updates using Server-Sent Events (SSE).",
    response_description="SSE stream of progress events",
    responses={
        200: {
            "description": "SSE stream started",
            "content": {
                "text/event-stream": {
                    "example": "event: progress\ndata: {\"percentage\": 45.5, \"stage\": \"encoding\"}\n\n"
                }
            }
        },
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to this job"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
    tags=["jobs"],
)
async def job_events(
    job_id: Annotated[UUID, Doc("Unique job identifier")],
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
):
    """
    Stream job progress events using Server-Sent Events.

    Events include:
    - `progress`: Periodic progress updates with percentage, stage, FPS
    - `completed`: Job completed successfully
    - `failed`: Job failed with error details
    - `cancelled`: Job was cancelled

    The stream ends when the job reaches a terminal state.
    """
    # Verify job exists and user has access
    job = await db.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Job not found"}
        )

    if job.api_key != api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "access_denied", "message": "Access denied"}
        )

    async def event_generator():
        """Generate SSE events for job progress."""
        last_progress = -1

        while True:
            # Refresh job from database
            await db.refresh(job)

            # Send progress update if changed
            if job.progress != last_progress:
                last_progress = job.progress

                progress_data = JobProgress(
                    percentage=job.progress,
                    stage=job.stage,
                    fps=job.fps,
                    eta_seconds=job.eta_seconds,
                )

                # Add quality metrics if available
                if job.vmaf_score or job.psnr_score:
                    progress_data.quality = {}
                    if job.vmaf_score:
                        progress_data.quality["vmaf"] = job.vmaf_score
                    if job.psnr_score:
                        progress_data.quality["psnr"] = job.psnr_score

                yield f"event: progress\ndata: {progress_data.model_dump_json()}\n\n"

            # Check if job completed
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                # Send final event
                final_event = {
                    "status": job.status,
                    "message": "Job completed" if job.status == JobStatus.COMPLETED else f"Job {job.status}",
                }

                if job.status == JobStatus.COMPLETED:
                    final_event["output_path"] = job.output_path
                    if job.output_metadata:
                        final_event["output_size"] = job.output_metadata.get("size")
                elif job.status == JobStatus.FAILED:
                    final_event["error"] = job.error_message

                yield f"event: {job.status.lower()}\ndata: {json.dumps(final_event)}\n\n"
                break

            # Wait before next check
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@router.get(
    "/jobs/{job_id}/logs",
    status_code=status.HTTP_200_OK,
    summary="Get job logs",
    description="Get FFmpeg processing logs for a job.",
    response_description="Job processing logs",
    responses={
        200: {"description": "Logs retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to this job"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
    tags=["jobs"],
)
async def get_job_logs(
    job_id: Annotated[UUID, Doc("Unique job identifier")],
    lines: Annotated[
        int,
        Query(ge=1, le=1000, description="Number of log lines to return"),
        Doc("Maximum number of log lines")
    ] = 100,
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> dict:
    """
    Get FFmpeg processing logs for a job.

    Returns the last N lines of processing logs.
    For running jobs, returns live logs from the worker.
    For completed jobs, returns stored logs.
    """
    # Get job
    job = await db.get(Job, job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"error": "not_found", "message": "Job not found"}
        )

    # Check ownership
    if job.api_key != api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "access_denied", "message": "Access denied"}
        )

    # Get logs from worker or storage
    logs = []

    if job.status == JobStatus.PROCESSING and job.worker_id:
        # Get live logs from worker
        logs = await queue_service.get_worker_logs(job.worker_id, str(job_id), lines)
    else:
        # Get stored logs from database and log aggregation system
        from api.services.job_service import JobService

        stored_logs = await JobService.get_job_logs(db, job_id, lines)

        if stored_logs:
            logs = stored_logs
        else:
            # Fallback to basic job information if no detailed logs available
            logs = [
                f"[{job.created_at.isoformat()}] Job created: {job_id}",
                f"[{job.created_at.isoformat()}] Status: {job.status.value}",
                f"[{job.created_at.isoformat()}] Input: {job.input_path or 'N/A'}",
                f"[{job.created_at.isoformat()}] Output: {job.output_path or 'N/A'}",
            ]

            if job.started_at:
                logs.append(f"[{job.started_at.isoformat()}] Processing started")

            if job.completed_at:
                logs.append(f"[{job.completed_at.isoformat()}] Processing completed")

            if job.error_message:
                logs.append(f"[{(job.completed_at or job.started_at or job.created_at).isoformat()}] ERROR: {job.error_message}")

            if job.progress > 0:
                logs.append(f"[{(job.completed_at or job.started_at or job.created_at).isoformat()}] Progress: {job.progress}%")

    return {
        "job_id": str(job_id),
        "lines": len(logs),
        "logs": logs,
    }
