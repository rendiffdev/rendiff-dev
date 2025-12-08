"""
Production-grade configuration management for Rendiff FFmpeg API.

Handles all application settings with validation, type safety, and environment-based configuration.
"""
import os
from functools import lru_cache
from pathlib import Path
from typing import List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra fields in .env file
    )
    
    # Application
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    TESTING: bool = False
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 4
    API_RELOAD: bool = False
    API_LOG_LEVEL: str = "info"
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/rendiff.db"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40
    
    # Queue
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_MAX_CONNECTIONS: int = 100
    
    # Storage
    STORAGE_CONFIG: str = "/app/config/storage.yml"
    STORAGE_PATH: str = "./storage"
    TEMP_PATH: str = "/tmp/rendiff"
    
    # Worker
    WORKER_TYPE: str = "cpu"  # cpu, gpu, or analysis
    WORKER_CONCURRENCY: int = 4
    WORKER_PREFETCH_MULTIPLIER: int = 1
    WORKER_MAX_TASKS_PER_CHILD: int = 100
    WORKER_TASK_TIME_LIMIT: int = 21600  # 6 hours
    
    # FFmpeg
    FFMPEG_THREADS: int = 0  # 0 = auto
    FFMPEG_PRESET: str = "medium"
    FFMPEG_CRF: int = 23
    FFMPEG_HARDWARE_ACCELERATION: str = "auto"
    
    # Security & Rate Limiting
    API_KEY_HEADER: str = "X-API-Key"
    ENABLE_API_KEYS: bool = True
    ENABLE_IP_WHITELIST: bool = False
    IP_WHITELIST: str = "10.0.0.0/8,192.168.0.0/16"
    ADMIN_API_KEYS: str = ""  # Comma-separated list of admin API keys
    
    # Rate Limiting
    ENABLE_RATE_LIMITING: bool = True
    RATE_LIMIT_CALLS: int = 2000
    RATE_LIMIT_PERIOD: int = 3600  # seconds
    
    # CORS
    CORS_ORIGINS: List[str] = Field(default_factory=lambda: ["http://localhost", "https://localhost"])
    
    # Monitoring
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9000
    ENABLE_TRACING: bool = False
    TRACING_ENDPOINT: Optional[str] = None
    
    # Resource Limits
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024 * 1024  # 10GB
    MAX_JOB_DURATION: int = 21600  # 6 hours
    MAX_CONCURRENT_JOBS_PER_KEY: int = 10
    MAX_OPERATIONS_PER_JOB: int = 50  # Maximum operations per conversion job
    JOB_RETENTION_DAYS: int = 7
    
    # Webhooks
    WEBHOOK_TIMEOUT: int = 30
    WEBHOOK_MAX_RETRIES: int = 3
    WEBHOOK_RETRY_DELAY: int = 60
    
    # Optional Services
    ENABLE_VIRUS_SCAN: bool = False
    CLAMAV_HOST: Optional[str] = None
    CLAMAV_PORT: int = 3310
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("TEMP_PATH", "STORAGE_PATH")
    def ensure_path_exists(cls, v):
        path = Path(v)
        path.mkdir(parents=True, exist_ok=True)
        return str(path)
    
    @property
    def ip_whitelist_parsed(self) -> List[str]:
        """Parse IP whitelist."""
        if not self.ENABLE_IP_WHITELIST:
            return []
        return [ip.strip() for ip in self.IP_WHITELIST.split(",")]
    
    @property
    def database_url_async(self) -> str:
        """Convert database URL to async version."""
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
        elif self.DATABASE_URL.startswith("sqlite://"):
            return self.DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
        return self.DATABASE_URL
    
    @property
    def VALKEY_URL(self) -> str:
        """Alias for REDIS_URL for compatibility with worker."""
        return self.REDIS_URL


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()