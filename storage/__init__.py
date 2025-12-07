"""
Storage module for managing multiple storage backends.

Supports local filesystem, S3-compatible storage, and other backends.
"""
from storage.base import StorageBackend
from storage.factory import create_storage_backend

__all__ = ["StorageBackend", "create_storage_backend"]
