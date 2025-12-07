"""
Celery tasks for processing jobs
"""
import asyncio
import json
import os
import tempfile
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, Optional

# Import removed - using internal FFmpeg wrapper instead
import structlog
import yaml
from celery import Task, current_task
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.config import settings
from api.models.job import Job, JobStatus
from storage.factory import create_storage_backend
from worker.processors.video import VideoProcessor
from worker.processors.analysis import AnalysisProcessor
from worker.utils.progress import ProgressTracker

logger = structlog.get_logger()


@lru_cache(maxsize=1)
def get_storage_config() -> Dict[str, Any]:
    """Load and cache storage configuration.

    Reads the YAML config file once and caches it to avoid
    synchronous I/O in async contexts.
    """
    with open(settings.STORAGE_CONFIG, 'r') as f:
        return yaml.safe_load(f)

# Database setup for worker
# Configure engine based on database type
if "sqlite" in settings.DATABASE_URL:
    # SQLite specific configuration
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True
    )
else:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class ProcessingError(Exception):
    """Custom exception for processing errors."""
    pass


def update_job_status(job_id: str, updates: Dict[str, Any]) -> None:
    """Update job status in database."""
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if job:
            for key, value in updates.items():
                setattr(job, key, value)
            db.commit()
    finally:
        db.close()


async def send_webhook(webhook_url: str, event: str, data: Dict[str, Any]) -> None:
    """Send webhook notification with retry logic."""
    if not webhook_url:
        return
    
    import asyncio
    import httpx
    
    max_retries = 3
    base_delay = 1  # Start with 1 second
    
    for attempt in range(max_retries + 1):
        try:
            timeout = httpx.Timeout(30.0)  # 30 second timeout
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(
                    webhook_url,
                    json=data,
                    headers={"Content-Type": "application/json", "User-Agent": "Rendiff-FFmpeg-API/1.0"}
                )
                
                if response.status_code < 300:
                    logger.info(f"Webhook sent successfully: {event} to {webhook_url}")
                    return
                else:
                    logger.warning(f"Webhook returned {response.status_code}: {event} to {webhook_url}")
                    
        except Exception as e:
            logger.warning(f"Webhook attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries:
                # Exponential backoff: 1s, 2s, 4s
                delay = base_delay * (2 ** attempt)
                await asyncio.sleep(delay)
            else:
                logger.error(f"Webhook permanently failed after {max_retries + 1} attempts: {webhook_url}")
                break


def process_job(job_id: str) -> Dict[str, Any]:
    """
    Main task for processing conversion jobs.
    """
    logger.info(f"Starting job processing: {job_id}")
    
    # Get job from database
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ProcessingError(f"Job {job_id} not found")
        
        # Update job status
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.worker_id = current_task.request.hostname
        db.commit()
        
        # Initialize progress tracker
        progress = ProgressTracker(job_id)
        
        # Process the job
        result = asyncio.run(process_job_async(job, progress))
        
        # Update job completion
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100.0
        job.processing_time = (job.completed_at - job.started_at).total_seconds()
        
        if result.get("vmaf_score"):
            job.vmaf_score = result["vmaf_score"]
        if result.get("psnr_score"):
            job.psnr_score = result["psnr_score"]
        
        db.commit()
        
        # Send webhook (async)
        if job.webhook_url:
            asyncio.run(send_webhook(job.webhook_url, "complete", {
                "job_id": str(job.id),
                "status": "completed",
                "output_path": job.output_path,
                "metrics": result.get("metrics", {}),
            }))
        
        logger.info(f"Job completed: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Job failed: {job_id}", error=str(e))
        
        # Update job failure
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            
            # Send webhook with sanitized error
            error_msg = "Processing failed"
            if "not found" in str(e).lower():
                error_msg = "Input file not found"
            elif "permission" in str(e).lower():
                error_msg = "Permission denied"
            elif "timeout" in str(e).lower():
                error_msg = "Processing timeout"
            else:
                error_msg = "Processing failed"

            asyncio.run(send_webhook(job.webhook_url, "error", {
                "job_id": str(job.id),
                "status": "failed",
                "error": error_msg,  # Sanitized error
            }))

        raise
    finally:
        db.close()


async def process_job_async(job: Job, progress: ProgressTracker) -> Dict[str, Any]:
    """
    Async job processing logic with proper cleanup.
    """
    import contextlib
    import shutil

    # Load storage configuration (cached)
    storage_config = get_storage_config()

    # Parse input/output paths
    input_backend_name, input_path = parse_storage_path(job.input_path)
    output_backend_name, output_path = parse_storage_path(job.output_path)
    
    # Create storage backends
    input_backend = create_storage_backend(
        storage_config["backends"][input_backend_name]
    )
    output_backend = create_storage_backend(
        storage_config["backends"][output_backend_name]
    )
    
    # Create temporary directory with guaranteed cleanup
    temp_dir = None
    try:
        temp_dir = tempfile.mkdtemp(prefix="rendiff_")
        temp_path = Path(temp_dir)
        
        # Download input file
        await progress.update(0, "downloading", "Downloading input file")
        local_input = temp_path / "input" / Path(input_path).name
        local_input.parent.mkdir(parents=True, exist_ok=True)
        
        # Use aiofiles for non-blocking file I/O
        import aiofiles
        async with await input_backend.read(input_path) as stream:
            async with aiofiles.open(local_input, 'wb') as f:
                async for chunk in stream:
                    await f.write(chunk)
        
        # Probe input file using internal wrapper
        await progress.update(10, "analyzing", "Analyzing input file")
        processor = VideoProcessor()
        await processor.initialize()
        video_info = await processor.get_video_info(str(local_input))
        
        # Prepare output path
        local_output = temp_path / "output" / Path(output_path).name
        local_output.parent.mkdir(parents=True, exist_ok=True)
        
        # Process file
        await progress.update(20, "processing", "Processing video")
        result = await processor.process(
            input_path=str(local_input),
            output_path=str(local_output),
            options=job.options,
            operations=job.operations,
            progress_callback=progress.ffmpeg_callback,
        )
        metrics = result.get('metrics', {})
        
        # Upload output file using async I/O
        await progress.update(90, "uploading", "Uploading output file")
        async with aiofiles.open(local_output, 'rb') as f:
            content = await f.read()
            await output_backend.write(output_path, content)
        
        # Complete
        await progress.update(100, "complete", "Processing complete")
        
        return {
            "output_path": job.output_path,
            "metrics": metrics,
            "vmaf_score": metrics.get("vmaf"),
            "psnr_score": metrics.get("psnr"),
        }
    finally:
        # Ensure temp directory is cleaned up
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to cleanup temp directory {temp_dir}: {e}")


def analyze_media(job_id: str) -> Dict[str, Any]:
    """
    Task for analyzing media quality metrics.
    """
    logger.info(f"Starting media analysis: {job_id}")
    
    # Similar structure to process_job but focused on analysis
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ProcessingError(f"Job {job_id} not found")
        
        # Run analysis
        processor = AnalysisProcessor()
        result = asyncio.run(processor.analyze(job))
        
        # Update job with results
        job.status = JobStatus.COMPLETED
        job.vmaf_score = result.get("vmaf")
        job.psnr_score = result.get("psnr")
        job.ssim_score = result.get("ssim")
        db.commit()
        
        return result
        
    except Exception as e:
        logger.error(f"Analysis failed: {job_id}", error=str(e))
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            db.commit()
        raise
    finally:
        db.close()


def create_streaming(job_id: str) -> Dict[str, Any]:
    """
    Task for creating streaming formats (HLS/DASH).
    """
    logger.info(f"Starting streaming creation: {job_id}")
    
    # Get job from database
    db = SessionLocal()
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            raise ProcessingError(f"Job {job_id} not found")
        
        # Update job status
        job.status = JobStatus.PROCESSING
        job.started_at = datetime.utcnow()
        job.worker_id = current_task.request.hostname
        db.commit()
        
        # Initialize progress tracker
        progress = ProgressTracker(job_id)
        
        # Process the streaming job
        result = asyncio.run(process_streaming_async(job, progress))
        
        # Update job completion
        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress = 100.0
        job.processing_time = (job.completed_at - job.started_at).total_seconds()
        
        db.commit()

        # Send webhook
        if job.webhook_url:
            asyncio.run(send_webhook(job.webhook_url, "complete", {
                "job_id": str(job.id),
                "status": "completed",
                "output_path": job.output_path,
                "streaming_info": result.get("streaming_info", {}),
            }))

        logger.info(f"Streaming job completed: {job_id}")
        return result
        
    except Exception as e:
        logger.error(f"Streaming job failed: {job_id}", error=str(e))
        
        # Update job failure
        if job:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            
            # Send webhook with sanitized error
            error_msg = "Processing failed"
            if "not found" in str(e).lower():
                error_msg = "Input file not found"
            elif "permission" in str(e).lower():
                error_msg = "Permission denied"
            elif "timeout" in str(e).lower():
                error_msg = "Processing timeout"
            else:
                error_msg = "Processing failed"

            asyncio.run(send_webhook(job.webhook_url, "error", {
                "job_id": str(job.id),
                "status": "failed",
                "error": error_msg,  # Sanitized error
            }))

        raise
    finally:
        db.close()


async def process_streaming_async(job: Job, progress: ProgressTracker) -> Dict[str, Any]:
    """
    Async streaming processing logic.
    """
    from worker.processors.streaming import StreamingProcessor

    # Load storage configuration (cached)
    storage_config = get_storage_config()

    # Parse input/output paths
    input_backend_name, input_path = parse_storage_path(job.input_path)
    output_backend_name, output_path = parse_storage_path(job.output_path)
    
    # Create storage backends
    input_backend = create_storage_backend(
        storage_config["backends"][input_backend_name]
    )
    output_backend = create_storage_backend(
        storage_config["backends"][output_backend_name]
    )
    
    # Create temporary directory for processing
    with tempfile.TemporaryDirectory(prefix="rendiff_streaming_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Download input file
        await progress.update(0, "downloading", "Downloading input file")
        local_input = temp_path / "input" / Path(input_path).name
        local_input.parent.mkdir(parents=True, exist_ok=True)
        
        # Use aiofiles for non-blocking file I/O
        import aiofiles
        async with await input_backend.read(input_path) as stream:
            async with aiofiles.open(local_input, 'wb') as f:
                async for chunk in stream:
                    await f.write(chunk)
        
        # Create streaming output directory
        await progress.update(10, "preparing", "Preparing streaming output")
        streaming_output_dir = temp_path / "streaming_output"
        streaming_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create streaming processor
        processor = StreamingProcessor()
        
        # Get streaming options from job
        streaming_options = job.options or {}
        format_type = streaming_options.get('format', 'hls')  # Default to HLS
        
        # Process streaming
        await progress.update(20, "processing", f"Creating {format_type.upper()} streaming format")
        streaming_result = await processor.create_streaming_package(
            input_path=str(local_input),
            output_dir=str(streaming_output_dir),
            format_type=format_type,
            options=streaming_options,
            progress_callback=progress.ffmpeg_callback,
        )
        
        # Validate streaming output
        await progress.update(80, "validating", "Validating streaming output")
        validation_result = await processor.validate_streaming_output(
            str(streaming_output_dir), format_type
        )
        
        if not validation_result['valid']:
            raise ProcessingError(f"Streaming validation failed: {validation_result['errors']}")
        
        # Upload streaming files to output backend
        await progress.update(85, "uploading", "Uploading streaming files")
        uploaded_files = []
        
        # Upload all generated files
        for file_path in validation_result['files_found']:
            rel_path = Path(file_path).relative_to(streaming_output_dir)
            output_file_path = f"{output_path}/{rel_path}"
            
            with open(file_path, 'rb') as f:
                await output_backend.write(output_file_path, f)
            
            uploaded_files.append(output_file_path)
        
        # Complete
        await progress.update(100, "complete", "Streaming creation complete")
        
        return {
            "output_path": job.output_path,
            "streaming_info": {
                "format": format_type,
                "files_created": len(uploaded_files),
                "uploaded_files": uploaded_files,
                "streaming_result": streaming_result,
                "validation": validation_result
            }
        }


def parse_storage_path(path: str) -> tuple[str, str]:
    """Parse storage path into backend name and path."""
    if "://" in path:
        parts = path.split("://", 1)
        return parts[0], parts[1]
    # Default to local storage
    return "local", path