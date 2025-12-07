"""
API Key model for authentication.
"""
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from api.models.database import Base


class APIKey(Base):
    """API Key model for authentication."""
    __tablename__ = "api_keys"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True, index=True)
    key_prefix = Column(String(8), nullable=False, index=True)
    
    # User/organization info
    user_id = Column(String(255), nullable=True)
    organization = Column(String(255), nullable=True)
    
    # Permissions and limits
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    max_concurrent_jobs = Column(Integer, default=5, nullable=False)
    monthly_limit_minutes = Column(Integer, default=10000, nullable=False)
    
    # Usage tracking
    total_requests = Column(Integer, default=0, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    
    # Lifecycle
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    description = Column(Text, nullable=True)
    created_by = Column(String(255), nullable=True)
    
    @classmethod
    def generate_key(cls) -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            tuple: (raw_key, key_hash, key_prefix) where raw_key should be shown to user only once
        """
        # Generate 32 random bytes (256 bits)
        raw_key = secrets.token_urlsafe(32)
        
        # Create hash for storage
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        
        # Get prefix for indexing (first 8 chars)
        key_prefix = raw_key[:8]
        
        return raw_key, key_hash, key_prefix
    
    @classmethod
    def hash_key(cls, raw_key: str) -> str:
        """Hash a raw key for comparison."""
        return hashlib.sha256(raw_key.encode()).hexdigest()
    
    def is_valid(self) -> bool:
        """Check if API key is valid (active, not expired, not revoked)."""
        now = datetime.utcnow()
        
        if not self.is_active:
            return False
            
        if self.revoked_at and self.revoked_at <= now:
            return False
            
        if self.expires_at and self.expires_at <= now:
            return False
            
        return True
    
    def is_expired(self) -> bool:
        """Check if API key is expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at
    
    def days_until_expiry(self) -> Optional[int]:
        """Get days until expiry, or None if no expiry set."""
        if not self.expires_at:
            return None
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)
    
    def update_last_used(self):
        """Update last used timestamp and increment request counter."""
        self.last_used_at = datetime.utcnow()
        self.total_requests += 1
    
    def revoke(self):
        """Revoke this API key."""
        self.revoked_at = datetime.utcnow()
        self.is_active = False
    
    def extend_expiry(self, days: int):
        """Extend expiry by specified days."""
        if self.expires_at:
            self.expires_at += timedelta(days=days)
        else:
            self.expires_at = datetime.utcnow() + timedelta(days=days)
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary for API responses."""
        data = {
            "id": str(self.id),
            "name": self.name,
            "key_prefix": self.key_prefix,
            "user_id": self.user_id,
            "organization": self.organization,
            "is_active": self.is_active,
            "is_admin": self.is_admin,
            "max_concurrent_jobs": self.max_concurrent_jobs,
            "monthly_limit_minutes": self.monthly_limit_minutes,
            "total_requests": self.total_requests,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "description": self.description,
            "created_by": self.created_by,
            "is_expired": self.is_expired(),
            "days_until_expiry": self.days_until_expiry(),
        }
        
        if include_sensitive:
            data["key_hash"] = self.key_hash
            
        return data
    
    def __repr__(self):
        return f"<APIKey {self.name} ({self.key_prefix}...)>"