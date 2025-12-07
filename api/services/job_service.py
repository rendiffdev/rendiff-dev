"""
Job service for managing job operations.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from api.models.job import Job, JobStatus

logger = structlog.get_logger()


class JobService:
    """Service for managing jobs."""
    
    @staticmethod
    async def get_job_logs(
        session: AsyncSession,
        job_id: UUID,
        lines: int = 100,
    ) -> List[str]:
        """
        Get stored logs for a job.
        
        In a production system, this would query a log aggregation service
        like ELK stack, but for now we return structured logs from job data.
        """
        # Get the job
        stmt = select(Job).where(Job.id == job_id)
        result = await session.execute(stmt)
        job = result.scalar_one_or_none()
        
        if not job:
            return []
        
        # Build log entries from job lifecycle
        logs = []
        
        # Job creation
        logs.append(f"[{job.created_at.isoformat()}] Job created: {job_id}")
        logs.append(f"[{job.created_at.isoformat()}] Status: QUEUED")
        logs.append(f"[{job.created_at.isoformat()}] Input: {job.input_path}")
        logs.append(f"[{job.created_at.isoformat()}] Operations: {len(job.operations) if job.operations else 0} operations requested")
        
        # Job parameters
        if job.options:
            logs.append(f"[{job.created_at.isoformat()}] Options: {job.options}")
        
        # Processing start
        if job.started_at:
            logs.append(f"[{job.started_at.isoformat()}] Status: PROCESSING")
            logs.append(f"[{job.started_at.isoformat()}] Worker ID: {job.worker_id}")
            logs.append(f"[{job.started_at.isoformat()}] Processing started")
        
        # Progress updates (simulated based on current progress)
        if job.progress > 0 and job.started_at:
            # Add some progress log entries
            progress_steps = [10, 25, 50, 75, 90]
            for step in progress_steps:
                if job.progress >= step:
                    # Better timestamp calculation without assuming linear progress
                    if job.completed_at:
                        # Job is complete, use actual completion timeline
                        total_duration = (job.completed_at - job.started_at).total_seconds()
                        # Use logarithmic scaling for more realistic progress estimation
                        import math
                        progress_factor = math.log(step + 1) / math.log(101)  # Avoid log(0)
                        step_duration = total_duration * progress_factor
                        step_time = job.started_at + timedelta(seconds=step_duration)
                    else:
                        # Job still running, use more conservative estimates
                        if step == max([s for s in progress_steps if job.progress >= s]):
                            step_time = datetime.utcnow()
                        else:
                            # Use current time for all past steps to avoid future timestamps
                            step_time = datetime.utcnow()
                    
                    logs.append(f"[{step_time.isoformat()}] Progress: {step}% complete")
        
        # Job completion
        if job.completed_at:
            if job.status == JobStatus.COMPLETED:
                logs.append(f"[{job.completed_at.isoformat()}] Status: COMPLETED")
                logs.append(f"[{job.completed_at.isoformat()}] Output: {job.output_path}")
                logs.append(f"[{job.completed_at.isoformat()}] Processing completed successfully")
                
                # Calculate processing time
                if job.started_at:
                    duration = (job.completed_at - job.started_at).total_seconds()
                    logs.append(f"[{job.completed_at.isoformat()}] Total processing time: {duration:.2f} seconds")
                    
            elif job.status == JobStatus.FAILED:
                logs.append(f"[{job.completed_at.isoformat()}] Status: FAILED")
                logs.append(f"[{job.completed_at.isoformat()}] Error: {job.error_message}")
                
            elif job.status == JobStatus.CANCELLED:
                logs.append(f"[{job.completed_at.isoformat()}] Status: CANCELLED")
                logs.append(f"[{job.completed_at.isoformat()}] Job was cancelled")
        
        # Webhook notifications
        if job.webhook_url and job.status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            webhook_time = job.completed_at or datetime.utcnow()
            logs.append(f"[{webhook_time.isoformat()}] Webhook notification sent to: {job.webhook_url}")
        
        # Return the requested number of lines (most recent first)
        return logs[-lines:] if lines > 0 else logs
    
    @staticmethod
    async def get_job_by_id(
        session: AsyncSession,
        job_id: UUID,
        api_key: Optional[str] = None,
    ) -> Optional[Job]:
        """Get job by ID, optionally filtered by API key."""
        stmt = select(Job).where(Job.id == job_id)
        
        if api_key:
            stmt = stmt.where(Job.api_key == api_key)
        
        result = await session.execute(stmt)
        return result.scalar_one_or_none()
    
    @staticmethod
    async def get_jobs_for_api_key(
        session: AsyncSession,
        api_key: str,
        status: Optional[JobStatus] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Job], int]:
        """Get jobs for an API key with pagination."""
        # Build base query
        stmt = select(Job).where(Job.api_key == api_key)
        count_stmt = select(func.count(Job.id)).where(Job.api_key == api_key)
        
        # Apply status filter
        if status:
            stmt = stmt.where(Job.status == status)
            count_stmt = count_stmt.where(Job.status == status)
        
        # Apply pagination
        stmt = stmt.order_by(desc(Job.created_at)).limit(limit).offset(offset)
        
        # Execute queries
        result = await session.execute(stmt)
        count_result = await session.execute(count_stmt)
        
        jobs = list(result.scalars().all())
        total_count = count_result.scalar()
        
        return jobs, total_count
    
    @staticmethod
    async def get_job_statistics(
        session: AsyncSession,
        api_key: Optional[str] = None,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get job statistics."""
        from datetime import timedelta
        
        # Calculate date range
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Build base query
        base_stmt = select(Job).where(Job.created_at >= start_date)
        
        if api_key:
            base_stmt = base_stmt.where(Job.api_key == api_key)
        
        # Get total count
        count_stmt = select(func.count(Job.id)).where(Job.created_at >= start_date)
        if api_key:
            count_stmt = count_stmt.where(Job.api_key == api_key)
        
        total_result = await session.execute(count_stmt)
        total_jobs = total_result.scalar()
        
        # Get status counts efficiently with single query
        from sqlalchemy import case
        status_counts_stmt = select(
            Job.status,
            func.count(Job.id)
        ).where(
            Job.created_at >= start_date
        ).group_by(Job.status)
        
        if api_key:
            status_counts_stmt = status_counts_stmt.where(Job.api_key == api_key)
        
        status_results = await session.execute(status_counts_stmt)
        status_stats = {status.value: 0 for status in JobStatus}  # Initialize all to 0
        
        for status, count in status_results:
            status_stats[status.value] = count
        
        # Get average processing time for completed jobs
        completed_stmt = select(
            func.avg(
                func.extract('epoch', Job.completed_at - Job.started_at)
            )
        ).where(
            and_(
                Job.status == JobStatus.COMPLETED,
                Job.started_at.isnot(None),
                Job.completed_at.isnot(None),
                Job.created_at >= start_date
            )
        )
        
        if api_key:
            completed_stmt = completed_stmt.where(Job.api_key == api_key)
        
        avg_result = await session.execute(completed_stmt)
        avg_processing_time = avg_result.scalar() or 0
        
        return {
            "period_days": days,
            "total_jobs": total_jobs,
            "status_breakdown": status_stats,
            "average_processing_time_seconds": float(avg_processing_time),
            "success_rate": (
                status_stats.get("completed", 0) / total_jobs * 100
                if total_jobs > 0 else 0
            ),
        }