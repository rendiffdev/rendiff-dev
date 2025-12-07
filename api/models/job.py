"""
Job models for database and API schemas.

Uses modern Pydantic 2.10+ patterns with:
- Enhanced Field documentation and examples
- JSON Schema customization for OpenAPI
- Strict validation modes
- Computed fields where appropriate
"""
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Annotated
from uuid import UUID, uuid4

from sqlalchemy import Column, String, JSON, DateTime, Float, Integer, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import TypeDecorator, CHAR
from pydantic import BaseModel, Field, ConfigDict, computed_field
from annotated_doc import Doc

Base = declarative_base()


class GUID(TypeDecorator):
    """Platform-agnostic GUID type for SQLite and PostgreSQL compatibility."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, UUID):
            return str(value)
        else:
            return str(UUID(value))

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return UUID(value)


class JobStatus(str, Enum):
    """Job processing status enumeration."""
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(str, Enum):
    """Job priority levels for queue ordering."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class Job(Base):
    """Database model for processing jobs."""
    __tablename__ = "jobs"

    id = Column(GUID(), primary_key=True, default=uuid4)
    status = Column(String, default=JobStatus.QUEUED, nullable=False, index=True)
    priority = Column(String, default=JobPriority.NORMAL, nullable=False)

    # Input/Output
    input_path = Column(String, nullable=False)
    output_path = Column(String, nullable=False)
    input_metadata = Column(JSON, default={})
    output_metadata = Column(JSON, default={})

    # Processing options
    options = Column(JSON, default={})
    operations = Column(JSON, default=[])

    # Progress tracking
    progress = Column(Float, default=0.0)
    stage = Column(String, default="queued")
    fps = Column(Float, nullable=True)
    eta_seconds = Column(Integer, nullable=True)

    # Quality metrics
    vmaf_score = Column(Float, nullable=True)
    psnr_score = Column(Float, nullable=True)
    ssim_score = Column(Float, nullable=True)

    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    # Error handling
    error_message = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)

    # Resource tracking
    worker_id = Column(String, nullable=True)
    processing_time = Column(Float, nullable=True)

    # API key tracking
    api_key = Column(String, nullable=True, index=True)

    # Webhook
    webhook_url = Column(String, nullable=True)
    webhook_events = Column(JSON, default=["complete", "error"])

    # Batch processing
    batch_id = Column(String, nullable=True, index=True)
    batch_index = Column(Integer, nullable=True)

    # Indexes
    __table_args__ = (
        Index("idx_job_status_created", "status", "created_at"),
        Index("idx_job_api_key_created", "api_key", "created_at"),
    )


# =============================================================================
# Pydantic schemas for API with FastAPI 0.124+ / Pydantic 2.10+ features
# =============================================================================

class ConvertRequest(BaseModel):
    """
    Request schema for media conversion endpoint.

    Supports flexible input/output specifications with various operations
    and processing options.
    """
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "input": "/storage/input/video.mp4",
                    "output": "/storage/output/video.webm",
                    "operations": [
                        {"type": "scale", "width": 1920, "height": 1080}
                    ],
                    "options": {"video_codec": "vp9", "audio_codec": "opus"},
                    "priority": "normal"
                }
            ]
        }
    )

    input: Annotated[
        str | Dict[str, Any],
        Field(
            description="Input file path or configuration object",
            examples=["/storage/input/video.mp4", {"path": "/storage/video.mp4", "backend": "s3"}]
        ),
        Doc("Source media file path or storage configuration")
    ]

    output: Annotated[
        str | Dict[str, Any],
        Field(
            description="Output file path or configuration object",
            examples=["/storage/output/video.webm"]
        ),
        Doc("Destination path for processed media")
    ]

    operations: Annotated[
        List[Dict[str, Any]],
        Field(
            default_factory=list,
            description="List of video/audio processing operations",
            examples=[
                [{"type": "scale", "width": 1920, "height": 1080}],
                [{"type": "trim", "start": 10, "duration": 30}]
            ]
        ),
        Doc("Processing operations to apply in sequence")
    ]

    options: Annotated[
        Dict[str, Any],
        Field(
            default_factory=dict,
            description="Additional processing options",
            examples=[{"video_codec": "h264", "crf": 23}]
        ),
        Doc("Codec and quality settings for the output")
    ]

    priority: Annotated[
        JobPriority,
        Field(
            default=JobPriority.NORMAL,
            description="Processing priority level"
        ),
        Doc("Queue priority: low, normal, or high")
    ]

    webhook_url: Annotated[
        Optional[str],
        Field(
            default=None,
            description="URL for status webhook notifications",
            examples=["https://api.example.com/webhooks/rendiff"]
        ),
        Doc("HTTPS URL to receive job status updates")
    ]

    webhook_events: Annotated[
        List[str],
        Field(
            default=["complete", "error"],
            description="Events that trigger webhook notifications"
        ),
        Doc("List of events: start, progress, complete, error")
    ]


class JobResponse(BaseModel):
    """Response schema for job information with computed properties."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "processing",
                    "priority": "normal",
                    "progress": 45.5,
                    "stage": "encoding",
                    "created_at": "2025-01-15T10:30:00Z",
                    "started_at": "2025-01-15T10:30:05Z",
                    "eta_seconds": 120,
                    "links": {
                        "self": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000",
                        "events": "/api/v1/jobs/550e8400-e29b-41d4-a716-446655440000/events"
                    }
                }
            ]
        }
    )

    id: Annotated[
        UUID,
        Field(description="Unique job identifier"),
        Doc("UUID v4 job identifier")
    ]

    status: Annotated[
        JobStatus,
        Field(description="Current job status"),
        Doc("Processing status: queued, processing, completed, failed, cancelled")
    ]

    priority: Annotated[
        JobPriority,
        Field(description="Job priority level"),
        Doc("Queue priority level")
    ]

    progress: Annotated[
        float,
        Field(ge=0, le=100, description="Processing progress percentage"),
        Doc("Completion percentage (0-100)")
    ]

    stage: Annotated[
        str,
        Field(description="Current processing stage"),
        Doc("Current stage: queued, downloading, encoding, uploading, complete")
    ]

    created_at: Annotated[
        datetime,
        Field(description="Job creation timestamp"),
        Doc("ISO 8601 timestamp when job was created")
    ]

    started_at: Annotated[
        Optional[datetime],
        Field(default=None, description="Processing start timestamp"),
        Doc("ISO 8601 timestamp when processing began")
    ]

    completed_at: Annotated[
        Optional[datetime],
        Field(default=None, description="Processing completion timestamp"),
        Doc("ISO 8601 timestamp when processing finished")
    ]

    eta_seconds: Annotated[
        Optional[int],
        Field(default=None, ge=0, description="Estimated time remaining in seconds"),
        Doc("Estimated seconds until completion")
    ]

    links: Annotated[
        Dict[str, str],
        Field(default_factory=dict, description="Related resource URLs"),
        Doc("HATEOAS links to related resources")
    ]

    error: Annotated[
        Optional[Dict[str, Any]],
        Field(default=None, description="Error details if job failed"),
        Doc("Error information including code and message")
    ]

    progress_details: Annotated[
        Optional[Dict[str, Any]],
        Field(default=None, description="Detailed progress information"),
        Doc("Extended progress data including fps, bitrate, size")
    ]

    @computed_field
    @property
    def is_complete(self) -> bool:
        """Whether the job has finished (success or failure)."""
        return self.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]

    @computed_field
    @property
    def duration_seconds(self) -> Optional[float]:
        """Processing duration in seconds if completed."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class JobProgress(BaseModel):
    """Real-time progress update schema for SSE/WebSocket."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "percentage": 45.5,
                    "stage": "encoding",
                    "fps": 60.2,
                    "bitrate": "5.2 Mbps",
                    "size_bytes": 52428800,
                    "eta_seconds": 120
                }
            ]
        }
    )

    percentage: Annotated[
        float,
        Field(ge=0, le=100, description="Progress percentage"),
        Doc("Current completion percentage")
    ]

    stage: Annotated[
        str,
        Field(description="Current processing stage"),
        Doc("Processing stage name")
    ]

    fps: Annotated[
        Optional[float],
        Field(default=None, ge=0, description="Current encoding FPS"),
        Doc("Frames per second being processed")
    ]

    bitrate: Annotated[
        Optional[str],
        Field(default=None, description="Current bitrate"),
        Doc("Output bitrate (e.g., '5.2 Mbps')")
    ]

    size_bytes: Annotated[
        Optional[int],
        Field(default=None, ge=0, description="Current output size in bytes"),
        Doc("Bytes written so far")
    ]

    time_elapsed: Annotated[
        Optional[float],
        Field(default=None, ge=0, description="Elapsed processing time"),
        Doc("Seconds since processing started")
    ]

    eta_seconds: Annotated[
        Optional[int],
        Field(default=None, ge=0, description="Estimated time remaining"),
        Doc("Estimated seconds until completion")
    ]

    quality: Annotated[
        Optional[Dict[str, float]],
        Field(default=None, description="Real-time quality metrics"),
        Doc("Quality scores if analysis is enabled")
    ]


class JobListResponse(BaseModel):
    """Paginated response for job listing with metadata."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "jobs": [],
                    "total": 150,
                    "page": 1,
                    "per_page": 20,
                    "has_next": True,
                    "has_prev": False
                }
            ]
        }
    )

    jobs: Annotated[
        List[JobResponse],
        Field(description="List of jobs for current page"),
        Doc("Array of job objects")
    ]

    total: Annotated[
        int,
        Field(ge=0, description="Total number of jobs matching query"),
        Doc("Total count across all pages")
    ]

    page: Annotated[
        int,
        Field(ge=1, description="Current page number"),
        Doc("Current page (1-indexed)")
    ]

    per_page: Annotated[
        int,
        Field(ge=1, le=100, description="Items per page"),
        Doc("Number of items per page")
    ]

    has_next: Annotated[
        bool,
        Field(description="Whether more pages exist"),
        Doc("True if there's a next page")
    ]

    has_prev: Annotated[
        bool,
        Field(description="Whether previous pages exist"),
        Doc("True if there's a previous page")
    ]

    @computed_field
    @property
    def total_pages(self) -> int:
        """Total number of pages."""
        return max(1, (self.total + self.per_page - 1) // self.per_page)


class JobCreateResponse(BaseModel):
    """Response after successfully creating a job."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "job": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "queued",
                        "priority": "normal",
                        "progress": 0,
                        "stage": "queued",
                        "created_at": "2025-01-15T10:30:00Z"
                    },
                    "estimated_cost": {
                        "processing_time": 120,
                        "credits": 0
                    },
                    "warnings": []
                }
            ]
        }
    )

    job: Annotated[
        JobResponse,
        Field(description="Created job details"),
        Doc("The newly created job object")
    ]

    estimated_cost: Annotated[
        Optional[Dict[str, Any]],
        Field(default=None, description="Estimated processing cost"),
        Doc("Processing time and resource estimates")
    ]

    warnings: Annotated[
        List[str],
        Field(default_factory=list, description="Non-critical warnings"),
        Doc("Warnings about the request (not errors)")
    ]


class ErrorResponse(BaseModel):
    """Standardized error response format."""
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error": {
                        "code": "validation_error",
                        "message": "Invalid input format",
                        "details": {"field": "input", "issue": "File not found"}
                    },
                    "request_id": "req_abc123"
                }
            ]
        }
    )

    error: Annotated[
        Dict[str, Any],
        Field(description="Error information"),
        Doc("Error details including code and message")
    ]

    request_id: Annotated[
        Optional[str],
        Field(default=None, description="Request identifier for debugging"),
        Doc("Unique request ID for support reference")
    ]
