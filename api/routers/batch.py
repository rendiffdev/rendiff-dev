"""
Batch processing endpoint - Multiple media file processing with FastAPI 0.124+ patterns.

Provides efficient batch job creation, status monitoring, and cancellation.
"""
from typing import Dict, Any, List, Annotated, Optional
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from annotated_doc import Doc
import structlog

from api.config import settings
from api.dependencies import DatabaseSession, RequiredAPIKey
from api.models.job import Job, JobStatus, JobResponse, ErrorResponse
from api.utils.validators import validate_input_path, validate_output_path, validate_operations
from api.utils.media_validator import media_validator
from pydantic import BaseModel, Field

logger = structlog.get_logger()
router = APIRouter()

# Lazy import to avoid circular dependency
def get_queue_service():
    from api.main import queue_service
    return queue_service

def get_storage_service():
    from api.main import storage_service
    return storage_service


class BatchJob(BaseModel):
    """Single job specification within a batch."""
    input: Annotated[str, Doc("Input file path or URI")]
    output: Annotated[str, Doc("Output file path or URI")]
    operations: Annotated[
        List[Dict[str, Any]],
        Doc("List of processing operations to apply")
    ] = []
    options: Annotated[
        Dict[str, Any],
        Doc("Additional processing options")
    ] = {}
    priority: Annotated[
        str,
        Doc("Job priority: low, normal, high")
    ] = "normal"


class BatchProcessRequest(BaseModel):
    """Batch processing request model."""
    jobs: Annotated[
        List[BatchJob],
        Field(min_length=1, max_length=100),
        Doc("List of jobs to process (1-100 jobs)")
    ]
    batch_name: Annotated[
        str,
        Doc("Optional name for this batch")
    ] = ""
    webhook_url: Annotated[
        Optional[str],
        Doc("URL to receive job completion notifications")
    ] = None
    webhook_events: Annotated[
        List[str],
        Doc("Events to send to webhook: started, progress, completed, failed")
    ] = []
    validate_files: Annotated[
        bool,
        Doc("Whether to validate input files before processing")
    ] = True

    model_config = {
        "json_schema_extra": {
            "example": {
                "jobs": [
                    {
                        "input": "s3://bucket/video1.mp4",
                        "output": "s3://bucket/output/video1_720p.mp4",
                        "operations": [{"type": "transcode", "video": {"resolution": "1280x720"}}],
                        "priority": "normal"
                    },
                    {
                        "input": "s3://bucket/video2.mp4",
                        "output": "s3://bucket/output/video2_720p.mp4",
                        "operations": [{"type": "transcode", "video": {"resolution": "1280x720"}}],
                        "priority": "normal"
                    }
                ],
                "batch_name": "720p conversion batch",
                "webhook_url": "https://example.com/webhook",
                "webhook_events": ["completed", "failed"],
                "validate_files": True
            }
        }
    }


class BatchProcessResponse(BaseModel):
    """Batch processing response model."""
    batch_id: Annotated[str, Doc("Unique batch identifier")]
    total_jobs: Annotated[int, Doc("Total number of jobs created")]
    jobs: Annotated[List[JobResponse], Doc("List of created job details")]
    estimated_cost: Annotated[Dict[str, Any], Doc("Cost and time estimates")]
    warnings: Annotated[List[str], Doc("Any warnings during batch creation")]


class BatchStatusResponse(BaseModel):
    """Batch status response model."""
    batch_id: Annotated[str, Doc("Unique batch identifier")]
    status: Annotated[str, Doc("Overall batch status")]
    progress: Annotated[float, Doc("Overall progress percentage")]
    statistics: Annotated[Dict[str, int], Doc("Job counts by status")]
    jobs: Annotated[List[Dict[str, Any]], Doc("Individual job details")]


class BatchCancelResponse(BaseModel):
    """Batch cancellation response model."""
    batch_id: Annotated[str, Doc("Unique batch identifier")]
    total_jobs: Annotated[int, Doc("Total jobs in batch")]
    cancelled: Annotated[int, Doc("Number of jobs cancelled")]
    failed_to_cancel: Annotated[int, Doc("Jobs that couldn't be cancelled")]
    message: Annotated[str, Doc("Status message")]


@router.post(
    "/batch",
    response_model=BatchProcessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create batch job",
    description="Submit multiple media processing jobs in a single request for efficient batch processing.",
    response_description="Batch creation result with job IDs",
    responses={
        201: {"description": "Batch created successfully"},
        400: {
            "model": ErrorResponse,
            "description": "Invalid request (empty batch, validation failures)",
            "content": {
                "application/json": {
                    "example": {"error": "validation_error", "message": "Batch size exceeds maximum of 100 jobs"}
                }
            }
        },
        401: {"model": ErrorResponse, "description": "Authentication required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    tags=["batch"],
)
async def create_batch_job(
    request: Annotated[BatchProcessRequest, Doc("Batch processing request")],
    background_tasks: BackgroundTasks,
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> BatchProcessResponse:
    """
    Create a batch of media processing jobs.

    This endpoint allows submitting multiple jobs at once for efficient processing.
    Jobs in a batch can have different operations and priorities.

    Features:
    - Batch file validation before processing
    - Per-job operation customization
    - Webhook notifications for batch events
    - Cost estimation for the entire batch
    """
    try:
        if not request.jobs:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "validation_error", "message": "No jobs provided in batch"}
            )

        if len(request.jobs) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "validation_error", "message": "Batch size exceeds maximum of 100 jobs"}
            )

        batch_id = str(uuid4())
        created_jobs = []
        warnings = []
        total_estimated_time = 0

        logger.info(
            "Starting batch job creation",
            batch_id=batch_id,
            total_jobs=len(request.jobs),
            api_key=api_key[:8] + "..." if len(api_key) > 8 else api_key
        )

        # Validate all files first if requested
        if request.validate_files:
            file_paths = [job.input for job in request.jobs]

            # Get API key tier for validation limits
            api_key_tier = _get_api_key_tier(api_key)

            validation_results = await media_validator.validate_batch_files(
                file_paths, api_key_tier
            )

            if validation_results['invalid_files'] > 0:
                invalid_files = [
                    r for r in validation_results['results']
                    if r['status'] == 'invalid'
                ]
                warnings.append(f"Found {len(invalid_files)} invalid files in batch")

                # Fail the entire batch if all files are invalid
                if len(invalid_files) == len(request.jobs):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={"error": "validation_error", "message": "All files in batch failed validation"}
                    )

        # Create individual jobs
        for i, job_request in enumerate(request.jobs):
            try:
                # Validate paths
                input_backend, input_validated = await validate_input_path(
                    job_request.input, storage_service
                )
                output_backend, output_validated = await validate_output_path(
                    job_request.output, storage_service
                )

                # Validate operations
                operations_validated = validate_operations(job_request.operations)

                # Create job record
                job = Job(
                    id=uuid4(),
                    status=JobStatus.QUEUED,
                    priority=job_request.priority,
                    input_path=input_validated,
                    output_path=output_validated,
                    options=job_request.options,
                    operations=operations_validated,
                    api_key=api_key,
                    webhook_url=request.webhook_url,
                    webhook_events=request.webhook_events,
                    batch_id=batch_id,
                    batch_index=i,
                )

                # Add to database
                db.add(job)
                await db.commit()
                await db.refresh(job)

                # Queue the job
                await get_queue_service().enqueue_job(
                    job_id=str(job.id),
                    priority=job_request.priority,
                )

                # Create job response
                job_response = JobResponse(
                    id=job.id,
                    status=job.status,
                    priority=job.priority,
                    progress=0.0,
                    stage="queued",
                    created_at=job.created_at,
                    links={
                        "self": f"/api/v1/jobs/{job.id}",
                        "events": f"/api/v1/jobs/{job.id}/events",
                        "logs": f"/api/v1/jobs/{job.id}/logs",
                        "cancel": f"/api/v1/jobs/{job.id}",
                        "batch": f"/api/v1/batch/{batch_id}"
                    },
                )

                created_jobs.append(job_response)

                # Estimate processing time
                estimated_time = _estimate_job_time(job_request)
                total_estimated_time += estimated_time

                logger.info(
                    "Batch job created",
                    job_id=str(job.id),
                    batch_id=batch_id,
                    batch_index=i,
                    input_path=job_request.input[:50] + "..." if len(job_request.input) > 50 else job_request.input
                )

            except Exception as e:
                logger.error(
                    "Failed to create batch job",
                    batch_id=batch_id,
                    batch_index=i,
                    error=str(e)
                )
                warnings.append(f"Job {i + 1} failed to create: {str(e)}")

        if not created_jobs:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": "batch_creation_failed", "message": "Failed to create any jobs in batch"}
            )

        # Estimate cost
        estimated_cost = {
            "processing_time_seconds": total_estimated_time,
            "credits": 0,  # For self-hosted, no credits
            "jobs_created": len(created_jobs),
            "jobs_failed": len(request.jobs) - len(created_jobs)
        }

        logger.info(
            "Batch job creation completed",
            batch_id=batch_id,
            jobs_created=len(created_jobs),
            total_estimated_time=total_estimated_time
        )

        return BatchProcessResponse(
            batch_id=batch_id,
            total_jobs=len(created_jobs),
            jobs=created_jobs,
            estimated_cost=estimated_cost,
            warnings=warnings
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Batch job creation failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to create batch job"}
        )


@router.get(
    "/batch/{batch_id}",
    response_model=BatchStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Get batch status",
    description="Get the current status and progress of all jobs in a batch.",
    response_description="Batch status with individual job progress",
    responses={
        200: {"description": "Batch status retrieved successfully"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to this batch"},
        404: {
            "model": ErrorResponse,
            "description": "Batch not found",
            "content": {
                "application/json": {
                    "example": {"error": "not_found", "message": "Batch not found"}
                }
            }
        },
    },
    tags=["batch"],
)
async def get_batch_status(
    batch_id: Annotated[str, Doc("Unique batch identifier")],
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> BatchStatusResponse:
    """
    Get status of a batch job.

    Returns overall batch progress and status of each individual job.
    Only the API key that created the batch can view its status.
    """
    try:
        # Query all jobs in the batch
        from sqlalchemy import select
        result = await db.execute(
            select(Job).where(Job.batch_id == batch_id, Job.api_key == api_key)
        )
        batch_jobs = result.scalars().all()

        if not batch_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Batch not found"}
            )

        # Calculate batch statistics
        total_jobs = len(batch_jobs)
        completed_jobs = sum(1 for job in batch_jobs if job.status == JobStatus.COMPLETED)
        failed_jobs = sum(1 for job in batch_jobs if job.status == JobStatus.FAILED)
        processing_jobs = sum(1 for job in batch_jobs if job.status == JobStatus.PROCESSING)
        queued_jobs = sum(1 for job in batch_jobs if job.status == JobStatus.QUEUED)

        # Calculate overall progress
        total_progress = sum(job.progress or 0 for job in batch_jobs)
        overall_progress = total_progress / total_jobs if total_jobs > 0 else 0

        # Determine batch status
        if completed_jobs == total_jobs:
            batch_status = "completed"
        elif failed_jobs == total_jobs:
            batch_status = "failed"
        elif failed_jobs > 0 and completed_jobs + failed_jobs == total_jobs:
            batch_status = "partial_success"
        elif processing_jobs > 0 or queued_jobs > 0:
            batch_status = "processing"
        else:
            batch_status = "unknown"

        return BatchStatusResponse(
            batch_id=batch_id,
            status=batch_status,
            progress=overall_progress,
            statistics={
                "total_jobs": total_jobs,
                "completed": completed_jobs,
                "failed": failed_jobs,
                "processing": processing_jobs,
                "queued": queued_jobs
            },
            jobs=[
                {
                    "id": str(job.id),
                    "status": job.status,
                    "progress": job.progress or 0,
                    "created_at": job.created_at,
                    "started_at": job.started_at,
                    "completed_at": job.completed_at,
                    "input_path": job.input_path,
                    "output_path": job.output_path
                }
                for job in sorted(batch_jobs, key=lambda x: x.batch_index or 0)
            ]
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get batch status", batch_id=batch_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to get batch status"}
        )


@router.delete(
    "/batch/{batch_id}",
    response_model=BatchCancelResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel batch",
    description="Cancel all queued and processing jobs in a batch.",
    response_description="Batch cancellation result",
    responses={
        200: {"description": "Batch cancellation processed"},
        401: {"model": ErrorResponse, "description": "Authentication required"},
        403: {"model": ErrorResponse, "description": "Access denied to this batch"},
        404: {"model": ErrorResponse, "description": "Batch not found"},
    },
    tags=["batch"],
)
async def cancel_batch(
    batch_id: Annotated[str, Doc("Unique batch identifier to cancel")],
    db: DatabaseSession = None,
    api_key: RequiredAPIKey = None,
) -> BatchCancelResponse:
    """
    Cancel all jobs in a batch.

    Only queued and processing jobs can be cancelled.
    Already completed or failed jobs are not affected.
    """
    try:
        # Query all jobs in the batch
        from sqlalchemy import select, update
        result = await db.execute(
            select(Job).where(Job.batch_id == batch_id, Job.api_key == api_key)
        )
        batch_jobs = result.scalars().all()

        if not batch_jobs:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error": "not_found", "message": "Batch not found"}
            )

        cancelled_count = 0
        failed_to_cancel = 0

        for job in batch_jobs:
            if job.status in [JobStatus.QUEUED, JobStatus.PROCESSING]:
                try:
                    # Cancel job in queue
                    if job.status == JobStatus.QUEUED:
                        success = await get_queue_service().cancel_job(str(job.id))
                    else:  # PROCESSING
                        success = await get_queue_service().cancel_running_job(
                            str(job.id),
                            job.worker_id or ""
                        )

                    if success:
                        # Update job status
                        await db.execute(
                            update(Job)
                            .where(Job.id == job.id)
                            .values(status=JobStatus.CANCELLED)
                        )
                        cancelled_count += 1
                    else:
                        failed_to_cancel += 1

                except Exception as e:
                    logger.error(
                        "Failed to cancel job in batch",
                        job_id=str(job.id),
                        batch_id=batch_id,
                        error=str(e)
                    )
                    failed_to_cancel += 1

        await db.commit()

        return BatchCancelResponse(
            batch_id=batch_id,
            total_jobs=len(batch_jobs),
            cancelled=cancelled_count,
            failed_to_cancel=failed_to_cancel,
            message=f"Cancelled {cancelled_count} jobs in batch"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to cancel batch", batch_id=batch_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "message": "Failed to cancel batch"}
        )


def _get_api_key_tier(api_key: str) -> str:
    """Determine API key tier from key prefix."""
    if api_key.startswith('ent_'):
        return 'enterprise'
    elif api_key.startswith('prem_'):
        return 'premium'
    elif api_key.startswith('basic_'):
        return 'basic'
    else:
        return 'free'


def _estimate_job_time(job_request: BatchJob) -> int:
    """Estimate processing time for a single job in seconds."""
    base_time = 60  # Base processing time

    # Add time based on operations
    for operation in job_request.operations:
        op_type = operation.get('type', '')
        if op_type == 'streaming':
            base_time += 300  # Streaming takes longer
        elif op_type == 'transcode':
            base_time += 120  # Transcoding time
        elif op_type in ['watermark', 'filter']:
            base_time += 60   # Filter operations
        else:
            base_time += 30   # Other operations

    return base_time
