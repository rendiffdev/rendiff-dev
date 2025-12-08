"""
Rendiff Worker - Processes FFmpeg jobs
"""
import asyncio
import signal
import sys
from typing import Optional

from celery import Celery
from celery.signals import worker_ready, worker_shutdown
import structlog

from api.config import settings
from worker.tasks import process_job, analyze_media, create_streaming
from api.utils.logger import setup_logging

# Setup logging
setup_logging()
logger = structlog.get_logger()

# Create Celery app
app = Celery(
    "rendiff_worker",
    broker=settings.VALKEY_URL,
    backend=settings.VALKEY_URL,
)

# Configure Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.WORKER_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.WORKER_TASK_TIME_LIMIT - 300,  # 5 min grace
    worker_prefetch_multiplier=settings.WORKER_PREFETCH_MULTIPLIER,
    worker_max_tasks_per_child=settings.WORKER_MAX_TASKS_PER_CHILD,
    task_acks_late=True,
    task_reject_on_worker_lost=False,  # Avoid conflicts with acks_late
    task_routes={
        "worker.process_job": {"queue": "default"},
        "worker.analyze_media": {"queue": "analysis"},
        "worker.create_streaming": {"queue": "streaming"},
    },
)

# Register tasks
app.task(name="worker.process_job")(process_job)
app.task(name="worker.analyze_media")(analyze_media)
app.task(name="worker.create_streaming")(create_streaming)


@worker_ready.connect
def on_worker_ready(**kwargs):
    """Called when worker is ready to accept tasks."""
    logger.info(
        "Worker ready",
        worker_type=getattr(settings, "WORKER_TYPE", "cpu"),
        concurrency=settings.WORKER_CONCURRENCY,
        hostname=kwargs.get("sender").hostname,
    )


@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """Called when worker is shutting down."""
    logger.info("Worker shutting down")


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    # Setup signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Determine worker type and queues
    worker_type = getattr(settings, "WORKER_TYPE", "cpu")
    
    if worker_type == "gpu":
        queues = ["gpu", "default"]
        concurrency = min(settings.WORKER_CONCURRENCY, 2)  # Limit GPU workers
    elif worker_type == "analysis":
        queues = ["analysis"]
        concurrency = settings.WORKER_CONCURRENCY
    else:
        queues = ["default", "streaming"]
        concurrency = settings.WORKER_CONCURRENCY
    
    logger.info(
        "Starting worker",
        worker_type=worker_type,
        queues=queues,
        concurrency=concurrency,
    )
    
    # Start worker
    app.worker_main([
        "worker",
        "--loglevel=info",
        f"--concurrency={concurrency}",
        f"--queues={','.join(queues)}",
        "--without-gossip",
        "--without-mingle",
        "--without-heartbeat",
    ])