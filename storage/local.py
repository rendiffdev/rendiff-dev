"""
Local filesystem storage backend.
"""
import os
import asyncio
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from storage.base import StorageBackend


class LocalStorageBackend(StorageBackend):
    """Local filesystem storage backend."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local storage backend.

        Args:
            config: Configuration with:
                - base_path: Root directory for storage
                - name: Backend name (optional)
        """
        super().__init__(config)
        self.base_path = Path(config.get("base_path", "/storage")).resolve()

        # Ensure base path exists
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve and validate a path.

        Args:
            path: Relative path within the storage

        Returns:
            Absolute Path object

        Raises:
            ValueError: If path would escape base directory
        """
        # Handle empty path
        if not path:
            return self.base_path

        # Resolve the full path
        full_path = (self.base_path / path).resolve()

        # Security check: ensure path is within base_path
        try:
            full_path.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path '{path}' would escape storage directory")

        return full_path

    async def exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            full_path = self._resolve_path(path)
            return await aiofiles.os.path.exists(full_path)
        except ValueError:
            return False

    async def read(self, path: str) -> AsyncIterator[bytes]:
        """Read file as async iterator of chunks."""
        full_path = self._resolve_path(path)

        if not await aiofiles.os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {path}")

        chunk_size = 8192  # 8KB chunks

        async with aiofiles.open(full_path, 'rb') as f:
            while True:
                chunk = await f.read(chunk_size)
                if not chunk:
                    break
                yield chunk

    async def write(self, path: str, data: Union[bytes, AsyncIterator[bytes]]) -> int:
        """Write data to file."""
        full_path = self._resolve_path(path)

        # Ensure parent directory exists
        await self.ensure_dir(str(full_path.parent.relative_to(self.base_path)))

        bytes_written = 0

        async with aiofiles.open(full_path, 'wb') as f:
            if isinstance(data, bytes):
                await f.write(data)
                bytes_written = len(data)
            else:
                # Handle async iterator
                async for chunk in data:
                    await f.write(chunk)
                    bytes_written += len(chunk)

        return bytes_written

    async def delete(self, path: str) -> bool:
        """Delete a file."""
        try:
            full_path = self._resolve_path(path)

            if not await aiofiles.os.path.exists(full_path):
                return False

            if await aiofiles.os.path.isdir(full_path):
                # Remove directory recursively
                import shutil
                await asyncio.to_thread(shutil.rmtree, full_path)
            else:
                await aiofiles.os.remove(full_path)

            return True
        except (OSError, ValueError):
            return False

    async def list(self, path: str = "", recursive: bool = False) -> List[str]:
        """List files in directory."""
        full_path = self._resolve_path(path)

        if not await aiofiles.os.path.exists(full_path):
            return []

        if not await aiofiles.os.path.isdir(full_path):
            return [path] if path else []

        files = []

        if recursive:
            # Walk directory tree
            for root, dirs, filenames in os.walk(full_path):
                root_path = Path(root)
                for filename in filenames:
                    file_path = root_path / filename
                    rel_path = str(file_path.relative_to(self.base_path))
                    files.append(rel_path)
        else:
            # List immediate children
            entries = await aiofiles.os.listdir(full_path)
            for entry in entries:
                entry_path = full_path / entry
                if path:
                    rel_path = f"{path}/{entry}"
                else:
                    rel_path = entry
                files.append(rel_path)

        return sorted(files)

    async def ensure_dir(self, path: str) -> None:
        """Ensure directory exists."""
        if not path:
            return

        full_path = self._resolve_path(path)

        if not await aiofiles.os.path.exists(full_path):
            await aiofiles.os.makedirs(full_path, exist_ok=True)

    async def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get file metadata."""
        try:
            full_path = self._resolve_path(path)

            if not await aiofiles.os.path.exists(full_path):
                return None

            stat = await aiofiles.os.stat(full_path)

            return {
                "path": path,
                "exists": True,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "is_dir": await aiofiles.os.path.isdir(full_path),
            }
        except (OSError, ValueError):
            return None

    async def get_size(self, path: str) -> int:
        """Get file size in bytes."""
        info = await self.get_file_info(path)
        return info.get("size", 0) if info else 0

    async def get_status(self) -> Dict[str, Any]:
        """Get backend status."""
        import shutil

        # Get disk usage
        try:
            usage = await asyncio.to_thread(shutil.disk_usage, self.base_path)
            disk_info = {
                "total": usage.total,
                "used": usage.used,
                "free": usage.free,
                "percent_used": round((usage.used / usage.total) * 100, 2),
            }
        except OSError:
            disk_info = {"error": "Unable to get disk usage"}

        return {
            "name": self.name,
            "type": "filesystem",
            "base_path": str(self.base_path),
            "available": self.base_path.exists(),
            "disk": disk_info,
        }
