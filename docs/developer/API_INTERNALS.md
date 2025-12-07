# API Internals

Deep dive into the Rendiff API implementation, covering request handling, middleware, authentication, and service architecture.

## Request Lifecycle

```
HTTP Request
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     MIDDLEWARE STACK                         │
├─────────────────────────────────────────────────────────────┤
│ 1. SecurityHeadersMiddleware    │ Add security headers      │
│ 2. InputSanitizationMiddleware  │ Validate content type     │
│ 3. RateLimitMiddleware          │ Check rate limits         │
│ 4. SecurityAuditMiddleware      │ Log security events       │
│ 5. CORSMiddleware               │ Handle CORS               │
│ 6. GZipMiddleware               │ Compress responses        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     DEPENDENCY INJECTION                     │
├─────────────────────────────────────────────────────────────┤
│ • Database Session (AsyncSession)                           │
│ • Redis Client                                              │
│ • Storage Service                                           │
│ • API Key Validation                                        │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│                     ROUTE HANDLER                            │
├─────────────────────────────────────────────────────────────┤
│ • Request validation (Pydantic)                             │
│ • Business logic execution                                  │
│ • Response serialization                                    │
└─────────────────────────────────────────────────────────────┘
    │
    ▼
HTTP Response
```

## Application Factory

The application is created using a factory pattern in `api/main.py`:

```python
def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    application = FastAPI(
        title="Rendiff API",
        description="Production-grade media processing API powered by FFmpeg",
        version=settings.VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Configure middleware (order matters!)
    _configure_middleware(application)

    # Register routers
    _register_routers(application)

    # Add exception handlers
    _register_exception_handlers(application)

    return application
```

### Lifespan Management

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Rendiff API", version=settings.VERSION)
    await initialize_database()
    await initialize_redis()
    await initialize_storage()

    yield  # Application runs

    # Shutdown
    logger.info("Shutting down Rendiff API")
    await close_database()
    await close_redis()
```

## Middleware Stack

### Security Headers Middleware

Adds security headers to all responses:

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    SECURITY_HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    }

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for header, value in self.SECURITY_HEADERS.items():
            response.headers[header] = value
        return response
```

### Rate Limit Middleware

Implements tiered rate limiting:

```python
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls: int = 100, period: int = 3600):
        super().__init__(app)
        self.calls = calls
        self.period = period
        self.redis = None

    async def dispatch(self, request: Request, call_next):
        # Extract client identifier
        client_id = self._get_client_id(request)

        # Check rate limit
        key = f"rate_limit:{client_id}"
        current = await self.redis.incr(key)

        if current == 1:
            await self.redis.expire(key, self.period)

        if current > self._get_limit(client_id):
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded"},
                headers={"Retry-After": str(self.period)}
            )

        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(self._get_limit(client_id))
        response.headers["X-RateLimit-Remaining"] = str(max(0, self._get_limit(client_id) - current))

        return response
```

### Rate Limit Tiers

| Tier | Identifier Pattern | Requests/Hour |
|------|-------------------|---------------|
| Basic | `basic_*` | 500 |
| Pro | `pro_*` | 2,000 |
| Enterprise | `ent_*` | 10,000 |
| Internal | `internal_*` | Unlimited |

## Dependency Injection

### Database Session

```python
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide database session with automatic cleanup."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### API Key Validation

```python
async def get_api_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Optional[APIKey]:
    """Validate and return API key from request."""
    if not settings.ENABLE_API_KEYS:
        return None

    api_key_header = request.headers.get("X-API-Key")
    if not api_key_header:
        raise HTTPException(
            status_code=401,
            detail="API key required"
        )

    # Constant-time comparison to prevent timing attacks
    api_key = await validate_api_key(db, api_key_header)
    if not api_key:
        # Add fixed delay to prevent timing attacks
        await asyncio.sleep(0.1)
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return api_key
```

### Storage Service

```python
async def get_storage_service() -> StorageService:
    """Provide storage service with configured backends."""
    return StorageService(settings.STORAGE_CONFIG)
```

## Router Structure

### Router Registration

```python
def _register_routers(app: FastAPI) -> None:
    """Register all API routers."""
    app.include_router(
        health_router,
        prefix="/api/v1",
        tags=["Health"]
    )
    app.include_router(
        jobs_router,
        prefix="/api/v1/jobs",
        tags=["Jobs"]
    )
    app.include_router(
        convert_router,
        prefix="/api/v1",
        tags=["Processing"]
    )
    if settings.ENABLE_ADMIN_ENDPOINTS:
        app.include_router(
            admin_router,
            prefix="/api/v1/admin",
            tags=["Admin"]
        )
```

### Convert Router Example

```python
# api/routers/convert.py

router = APIRouter()

@router.post(
    "/convert",
    response_model=JobResponse,
    status_code=201,
)
async def create_conversion_job(
    request: ConversionRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(get_api_key),
    storage: StorageService = Depends(get_storage_service),
) -> JobResponse:
    """Create a new media conversion job."""

    # 1. Validate input path
    input_backend, input_path = await validate_input_path(
        request.input_path, storage
    )

    # 2. Validate output path
    output_backend, output_path = await validate_output_path(
        request.output_path, storage
    )

    # 3. Validate operations
    validated_ops = validate_operations(request.operations or [])

    # 4. Create job record
    job = Job(
        input_path=request.input_path,
        output_path=request.output_path,
        operations=validated_ops,
        options=request.options,
        api_key=api_key.id if api_key else None,
        webhook_url=validate_webhook_url(request.webhook_url),
    )

    db.add(job)
    await db.flush()  # Get ID before commit

    # 5. Queue job for processing
    celery_app.send_task(
        "worker.tasks.process_job",
        args=[str(job.id)]
    )

    await db.commit()

    return JobResponse.from_orm(job)
```

## Request Validation

### Pydantic Models

```python
# api/schemas/conversion.py

class ConversionRequest(BaseModel):
    """Request schema for conversion endpoint."""

    input_path: str = Field(
        ...,
        description="Source file path (storage URI)",
        example="local:///storage/input.mp4"
    )
    output_path: str = Field(
        ...,
        description="Destination file path",
        example="local:///storage/output.mp4"
    )
    operations: Optional[List[OperationSchema]] = Field(
        default=[],
        description="Processing operations to apply"
    )
    options: Optional[ProcessingOptions] = Field(
        default=None,
        description="Global processing options"
    )
    webhook_url: Optional[str] = Field(
        default=None,
        description="URL for completion notification"
    )

    @validator("input_path", "output_path")
    def validate_storage_uri(cls, v):
        """Validate storage URI format."""
        if not re.match(r"^(local|s3|azure|gcs)://", v):
            raise ValueError("Invalid storage URI format")
        return v

    class Config:
        schema_extra = {
            "example": {
                "input_path": "local:///storage/input.mp4",
                "output_path": "local:///storage/output.webm",
                "operations": [
                    {"type": "transcode", "video_codec": "vp9"}
                ]
            }
        }
```

### Custom Validators

```python
# api/utils/validators.py

def validate_secure_path(path: str, base_paths: set = None) -> str:
    """
    Validate file path to prevent directory traversal.

    Security measures:
    1. Null byte detection
    2. Dangerous character blocking
    3. Path canonicalization
    4. Base path enforcement
    """
    if not path:
        raise SecurityError("Path cannot be empty")

    # Check for null bytes
    if "\x00" in path:
        raise SecurityError("Null byte detected in path")

    # Check for dangerous characters
    dangerous_chars = ["|", ";", "&", "$", "`", "<", ">", '"', "'"]
    for char in dangerous_chars:
        if char in path:
            raise SecurityError(f"Dangerous character: {char}")

    # Canonicalize path
    canonical = os.path.realpath(os.path.abspath(path))

    # Check for traversal after canonicalization
    if ".." in canonical:
        raise SecurityError("Directory traversal detected")

    # Verify against allowed base paths
    if base_paths:
        allowed = any(
            canonical.startswith(os.path.realpath(base) + os.sep)
            for base in base_paths
        )
        if not allowed:
            raise SecurityError("Path outside allowed directories")

    return canonical
```

## Error Handling

### Exception Handlers

```python
# api/utils/error_handlers.py

async def rendiff_exception_handler(
    request: Request,
    exc: RendiffError
) -> JSONResponse:
    """Handle Rendiff-specific exceptions."""
    logger.error(
        "Application error",
        error_code=exc.code,
        error_message=exc.message,
        path=request.url.path,
    )

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "type": type(exc).__name__,
            }
        }
    )

async def general_exception_handler(
    request: Request,
    exc: Exception
) -> JSONResponse:
    """Handle unexpected exceptions."""
    logger.error(
        "Unhandled exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        traceback=traceback.format_exc(),
    )

    # Don't expose internal details in production
    message = "An internal error occurred"
    if settings.DEBUG:
        message = str(exc)

    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": message,
            }
        }
    )
```

### Exception Hierarchy

```python
class RendiffError(Exception):
    """Base exception for all Rendiff errors."""

    def __init__(self, message: str, code: str, status_code: int = 500):
        self.message = message
        self.code = code
        self.status_code = status_code

class ValidationError(RendiffError):
    """Input validation errors (400)."""

    def __init__(self, message: str, field: str = None):
        super().__init__(message, "VALIDATION_ERROR", 400)
        self.field = field

class AuthenticationError(RendiffError):
    """Authentication errors (401)."""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(message, "AUTH_ERROR", 401)

class AuthorizationError(RendiffError):
    """Authorization errors (403)."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(message, "AUTHZ_ERROR", 403)

class RateLimitError(RendiffError):
    """Rate limit errors (429)."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, "RATE_LIMIT_ERROR", 429)

class ProcessingError(RendiffError):
    """Media processing errors (500)."""

    def __init__(self, message: str, job_id: str = None):
        super().__init__(message, "PROCESSING_ERROR", 500)
        self.job_id = job_id

class StorageError(RendiffError):
    """Storage backend errors (500)."""

    def __init__(self, message: str, backend: str = None):
        super().__init__(message, "STORAGE_ERROR", 500)
        self.backend = backend
```

## Response Serialization

### Response Models

```python
class JobResponse(BaseModel):
    """Job response schema."""

    id: UUID
    status: JobStatus
    progress: float
    input_path: str
    output_path: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True  # Enable ORM mode

class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response."""

    items: List[T]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool
```

## Database Operations

### Async Session Usage

```python
async def get_job_by_id(
    db: AsyncSession,
    job_id: UUID
) -> Optional[Job]:
    """Fetch job by ID."""
    result = await db.execute(
        select(Job).where(Job.id == job_id)
    )
    return result.scalar_one_or_none()

async def list_jobs(
    db: AsyncSession,
    api_key_id: UUID,
    status: Optional[JobStatus] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Job], int]:
    """List jobs with pagination."""
    query = select(Job).where(Job.api_key == api_key_id)

    if status:
        query = query.where(Job.status == status)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = await db.scalar(count_query)

    # Fetch page
    query = query.order_by(Job.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return jobs, total
```

## Background Tasks

### Celery Integration

```python
from worker.celery_app import celery_app

async def queue_processing_job(job_id: str, priority: str = "normal"):
    """Queue job for background processing."""
    queue = {
        "low": "rendiff.low",
        "normal": "rendiff.default",
        "high": "rendiff.high",
    }.get(priority, "rendiff.default")

    celery_app.send_task(
        "worker.tasks.process_job",
        args=[job_id],
        queue=queue,
    )
```

## Health Checks

```python
@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Comprehensive health check."""
    checks = {}

    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    # Redis check
    try:
        await redis.ping()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        checks["redis"] = {"status": "unhealthy", "error": str(e)}

    # FFmpeg check
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            timeout=5
        )
        checks["ffmpeg"] = {
            "status": "healthy" if result.returncode == 0 else "unhealthy"
        }
    except Exception as e:
        checks["ffmpeg"] = {"status": "unhealthy", "error": str(e)}

    overall = all(c["status"] == "healthy" for c in checks.values())

    return HealthResponse(
        status="healthy" if overall else "degraded",
        checks=checks,
        version=settings.VERSION,
    )
```

## Metrics

### Prometheus Metrics

```python
from prometheus_client import Counter, Histogram, Gauge

# Request metrics
REQUEST_COUNT = Counter(
    "rendiff_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status"]
)

REQUEST_LATENCY = Histogram(
    "rendiff_request_duration_seconds",
    "Request latency",
    ["method", "endpoint"]
)

# Job metrics
JOBS_TOTAL = Counter(
    "rendiff_jobs_total",
    "Total jobs created",
    ["status"]
)

JOBS_ACTIVE = Gauge(
    "rendiff_jobs_active",
    "Currently processing jobs"
)

JOB_DURATION = Histogram(
    "rendiff_job_duration_seconds",
    "Job processing duration",
    ["type"],
    buckets=[1, 5, 10, 30, 60, 300, 600, 1800, 3600]
)
```

## Configuration

### Settings Class

```python
class Settings(BaseSettings):
    """Application configuration."""

    # Application
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://..."
    DATABASE_POOL_SIZE: int = 20

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    ENABLE_API_KEYS: bool = True
    RATE_LIMIT_CALLS: int = 100
    RATE_LIMIT_PERIOD: int = 3600

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

settings = get_settings()
```
