"""
Google Cloud Storage backend.

Placeholder implementation - full implementation requires google-cloud-storage.
"""
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from storage.base import StorageBackend


class GCSStorageBackend(StorageBackend):
    """Google Cloud Storage backend."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize GCS storage backend.

        Args:
            config: Configuration with:
                - bucket: GCS bucket name
                - project: GCP project ID (optional)
                - credentials: Path to service account JSON (optional)
        """
        super().__init__(config)
        self.bucket = config.get("bucket")

        if not self.bucket:
            raise ValueError("GCS backend requires 'bucket' in configuration")

        # Check for google-cloud-storage
        try:
            from google.cloud import storage
            self._available = True
        except ImportError:
            self._available = False

    async def exists(self, path: str) -> bool:
        """Check if object exists."""
        if not self._available:
            raise ImportError("GCS storage requires google-cloud-storage. Install with: pip install google-cloud-storage")
        raise NotImplementedError("GCS storage backend not fully implemented")

    async def read(self, path: str) -> AsyncIterator[bytes]:
        """Read object as async iterator."""
        if not self._available:
            raise ImportError("GCS storage requires google-cloud-storage")
        raise NotImplementedError("GCS storage backend not fully implemented")

    async def write(self, path: str, data: Union[bytes, AsyncIterator[bytes]]) -> int:
        """Write data to object."""
        if not self._available:
            raise ImportError("GCS storage requires google-cloud-storage")
        raise NotImplementedError("GCS storage backend not fully implemented")

    async def delete(self, path: str) -> bool:
        """Delete an object."""
        if not self._available:
            raise ImportError("GCS storage requires google-cloud-storage")
        raise NotImplementedError("GCS storage backend not fully implemented")

    async def list(self, path: str = "", recursive: bool = False) -> List[str]:
        """List objects in bucket."""
        if not self._available:
            raise ImportError("GCS storage requires google-cloud-storage")
        raise NotImplementedError("GCS storage backend not fully implemented")

    async def ensure_dir(self, path: str) -> None:
        """GCS doesn't need directory creation."""
        pass

    async def get_status(self) -> Dict[str, Any]:
        """Get backend status."""
        return {
            "name": self.name,
            "type": "gcs",
            "bucket": self.bucket,
            "available": self._available,
            "implemented": False,
        }
