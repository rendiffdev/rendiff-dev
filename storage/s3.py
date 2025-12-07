"""
S3-compatible storage backend.

Supports AWS S3, MinIO, and other S3-compatible object stores.
"""
import asyncio
from io import BytesIO
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from storage.base import StorageBackend


class S3StorageBackend(StorageBackend):
    """S3-compatible storage backend."""

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize S3 storage backend.

        Args:
            config: Configuration with:
                - bucket: S3 bucket name
                - region: AWS region (optional)
                - endpoint_url: Custom endpoint for MinIO/compatible stores
                - access_key: AWS access key (optional, uses default credentials)
                - secret_key: AWS secret key (optional, uses default credentials)
                - prefix: Path prefix within bucket (optional)
        """
        super().__init__(config)
        self.bucket = config.get("bucket")
        self.region = config.get("region", "us-east-1")
        self.endpoint_url = config.get("endpoint_url")
        self.prefix = config.get("prefix", "").strip("/")

        if not self.bucket:
            raise ValueError("S3 backend requires 'bucket' in configuration")

        self._client = None

    async def _get_client(self):
        """Get or create S3 client."""
        if self._client is None:
            try:
                import aioboto3
            except ImportError:
                raise ImportError(
                    "S3 storage requires aioboto3. Install with: pip install aioboto3"
                )

            session = aioboto3.Session()

            client_kwargs = {
                "region_name": self.region,
            }

            if self.endpoint_url:
                client_kwargs["endpoint_url"] = self.endpoint_url

            # Check for explicit credentials in config
            if self.config.get("access_key") and self.config.get("secret_key"):
                client_kwargs["aws_access_key_id"] = self.config["access_key"]
                client_kwargs["aws_secret_access_key"] = self.config["secret_key"]

            self._session = session
            self._client_kwargs = client_kwargs

        return self._session.client("s3", **self._client_kwargs)

    def _full_path(self, path: str) -> str:
        """Get full path including prefix."""
        if not path:
            return self.prefix
        if self.prefix:
            return f"{self.prefix}/{path.lstrip('/')}"
        return path.lstrip("/")

    async def exists(self, path: str) -> bool:
        """Check if object exists."""
        try:
            async with await self._get_client() as client:
                await client.head_object(Bucket=self.bucket, Key=self._full_path(path))
                return True
        except Exception:
            return False

    async def read(self, path: str) -> AsyncIterator[bytes]:
        """Read object as async iterator of chunks."""
        async with await self._get_client() as client:
            response = await client.get_object(
                Bucket=self.bucket,
                Key=self._full_path(path)
            )

            async with response["Body"] as stream:
                chunk_size = 8192
                while True:
                    chunk = await stream.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk

    async def write(self, path: str, data: Union[bytes, AsyncIterator[bytes]]) -> int:
        """Write data to object."""
        # Collect data if it's an iterator
        if isinstance(data, bytes):
            content = data
        else:
            chunks = []
            async for chunk in data:
                chunks.append(chunk)
            content = b"".join(chunks)

        async with await self._get_client() as client:
            await client.put_object(
                Bucket=self.bucket,
                Key=self._full_path(path),
                Body=content
            )

        return len(content)

    async def delete(self, path: str) -> bool:
        """Delete an object."""
        try:
            async with await self._get_client() as client:
                await client.delete_object(
                    Bucket=self.bucket,
                    Key=self._full_path(path)
                )
                return True
        except Exception:
            return False

    async def list(self, path: str = "", recursive: bool = False) -> List[str]:
        """List objects in prefix."""
        prefix = self._full_path(path)
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        files = []
        delimiter = "" if recursive else "/"

        async with await self._get_client() as client:
            paginator = client.get_paginator("list_objects_v2")

            async for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=prefix,
                Delimiter=delimiter
            ):
                # Add files
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    # Remove prefix to get relative path
                    if self.prefix:
                        rel_path = key[len(self.prefix):].lstrip("/")
                    else:
                        rel_path = key
                    files.append(rel_path)

                # Add "directories" (common prefixes) if not recursive
                if not recursive:
                    for prefix_obj in page.get("CommonPrefixes", []):
                        pref = prefix_obj["Prefix"]
                        if self.prefix:
                            rel_path = pref[len(self.prefix):].strip("/")
                        else:
                            rel_path = pref.strip("/")
                        if rel_path:
                            files.append(rel_path + "/")

        return sorted(files)

    async def ensure_dir(self, path: str) -> None:
        """
        Ensure "directory" exists in S3.

        Note: S3 doesn't have real directories, but we create a placeholder
        object to simulate directory structure.
        """
        # S3 doesn't need explicit directory creation
        pass

    async def get_file_info(self, path: str) -> Optional[Dict[str, Any]]:
        """Get object metadata."""
        try:
            async with await self._get_client() as client:
                response = await client.head_object(
                    Bucket=self.bucket,
                    Key=self._full_path(path)
                )

                return {
                    "path": path,
                    "exists": True,
                    "size": response.get("ContentLength", 0),
                    "modified": response.get("LastModified"),
                    "etag": response.get("ETag", "").strip('"'),
                    "content_type": response.get("ContentType"),
                }
        except Exception:
            return None

    async def get_status(self) -> Dict[str, Any]:
        """Get backend status."""
        try:
            async with await self._get_client() as client:
                # Test access by listing bucket (limited to 1 object)
                await client.list_objects_v2(
                    Bucket=self.bucket,
                    MaxKeys=1
                )
                available = True
        except Exception as e:
            available = False

        return {
            "name": self.name,
            "type": "s3",
            "bucket": self.bucket,
            "region": self.region,
            "endpoint_url": self.endpoint_url,
            "prefix": self.prefix,
            "available": available,
        }

    async def cleanup(self) -> None:
        """Clean up S3 client."""
        self._client = None
