"""
Azure Blob Storage backend.

Placeholder implementation - full implementation requires azure-storage-blob.
"""
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from storage.base import StorageBackend


class AzureStorageBackend(StorageBackend):
    """Azure Blob Storage backend."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Azure storage backend.

        Args:
            config: Configuration with:
                - container: Azure container name
                - connection_string: Azure connection string
                - account_name: Storage account name (alternative to connection_string)
                - account_key: Storage account key (alternative to connection_string)
        """
        super().__init__(config)
        self.container = config.get("container")

        if not self.container:
            raise ValueError("Azure backend requires 'container' in configuration")

        # Check for azure-storage-blob
        try:
            from azure.storage.blob.aio import BlobServiceClient
            self._available = True
        except ImportError:
            self._available = False

    async def exists(self, path: str) -> bool:
        """Check if blob exists."""
        if not self._available:
            raise ImportError("Azure storage requires azure-storage-blob. Install with: pip install azure-storage-blob")
        raise NotImplementedError("Azure storage backend not fully implemented")

    async def read(self, path: str) -> AsyncIterator[bytes]:
        """Read blob as async iterator."""
        if not self._available:
            raise ImportError("Azure storage requires azure-storage-blob")
        raise NotImplementedError("Azure storage backend not fully implemented")

    async def write(self, path: str, data: Union[bytes, AsyncIterator[bytes]]) -> int:
        """Write data to blob."""
        if not self._available:
            raise ImportError("Azure storage requires azure-storage-blob")
        raise NotImplementedError("Azure storage backend not fully implemented")

    async def delete(self, path: str) -> bool:
        """Delete a blob."""
        if not self._available:
            raise ImportError("Azure storage requires azure-storage-blob")
        raise NotImplementedError("Azure storage backend not fully implemented")

    async def list(self, path: str = "", recursive: bool = False) -> List[str]:
        """List blobs in container."""
        if not self._available:
            raise ImportError("Azure storage requires azure-storage-blob")
        raise NotImplementedError("Azure storage backend not fully implemented")

    async def ensure_dir(self, path: str) -> None:
        """Azure doesn't need directory creation."""
        pass

    async def get_status(self) -> Dict[str, Any]:
        """Get backend status."""
        return {
            "name": self.name,
            "type": "azure",
            "container": self.container,
            "available": self._available,
            "implemented": False,
        }
