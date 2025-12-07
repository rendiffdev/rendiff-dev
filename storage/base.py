"""
Abstract base class for storage backends.
"""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, Union
from pathlib import Path


class StorageBackend(ABC):
    """Abstract base class for storage backends."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize storage backend.

        Args:
            config: Backend configuration dictionary
        """
        self.config = config
        self.name = config.get("name", "unknown")

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """
        Check if a file exists.

        Args:
            path: File path relative to backend root

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def read(self, path: str) -> AsyncIterator[bytes]:
        """
        Read file contents as an async iterator of chunks.

        Args:
            path: File path relative to backend root

        Yields:
            File content chunks as bytes
        """
        pass

    @abstractmethod
    async def write(self, path: str, data: Union[bytes, AsyncIterator[bytes]]) -> int:
        """
        Write data to a file.

        Args:
            path: File path relative to backend root
            data: File content as bytes or async iterator of chunks

        Returns:
            Number of bytes written
        """
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """
        Delete a file.

        Args:
            path: File path relative to backend root

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def list(self, path: str = "", recursive: bool = False) -> List[str]:
        """
        List files in a directory.

        Args:
            path: Directory path relative to backend root
            recursive: Whether to list recursively

        Returns:
            List of file paths
        """
        pass

    @abstractmethod
    async def ensure_dir(self, path: str) -> None:
        """
        Ensure a directory exists, creating it if necessary.

        Args:
            path: Directory path relative to backend root
        """
        pass

    async def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """
        Get file metadata.

        Args:
            path: File path relative to backend root

        Returns:
            Dictionary with file info or None if not found
        """
        if not await self.exists(path):
            return None
        return {
            "path": path,
            "exists": True,
        }

    async def get_size(self, path: str) -> int:
        """
        Get file size in bytes.

        Args:
            path: File path relative to backend root

        Returns:
            File size in bytes
        """
        info = await self.get_file_info(path)
        return info.get("size", 0) if info else 0

    async def get_status(self) -> Dict[str, Any]:
        """
        Get backend status.

        Returns:
            Dictionary with backend status information
        """
        return {
            "name": self.name,
            "type": self.__class__.__name__,
            "available": True,
        }

    async def cleanup(self) -> None:
        """Clean up backend resources."""
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
