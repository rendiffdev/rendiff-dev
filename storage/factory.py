"""
Factory for creating storage backends.
"""
from typing import Any, Dict

from storage.base import StorageBackend


def create_storage_backend(config: Dict[str, Any]) -> StorageBackend:
    """
    Create a storage backend from configuration.

    Args:
        config: Backend configuration dictionary with at least:
            - type: Backend type (filesystem, s3, azure, gcs)
            - name: Backend name for identification

    Returns:
        Configured StorageBackend instance

    Raises:
        ValueError: If backend type is unknown or config is invalid
    """
    backend_type = config.get("type", "").lower()

    if not backend_type:
        raise ValueError("Backend configuration must include 'type'")

    if backend_type in ("filesystem", "local", "file"):
        from storage.local import LocalStorageBackend
        return LocalStorageBackend(config)

    elif backend_type in ("s3", "aws", "minio"):
        from storage.s3 import S3StorageBackend
        return S3StorageBackend(config)

    elif backend_type in ("azure", "blob", "azure_blob"):
        from storage.azure import AzureStorageBackend
        return AzureStorageBackend(config)

    elif backend_type in ("gcs", "google", "google_cloud"):
        from storage.gcs import GCSStorageBackend
        return GCSStorageBackend(config)

    elif backend_type in ("nfs", "smb", "cifs", "network"):
        # Network storage uses local backend with network path
        from storage.local import LocalStorageBackend
        return LocalStorageBackend(config)

    else:
        raise ValueError(f"Unknown storage backend type: {backend_type}")
