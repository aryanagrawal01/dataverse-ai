from functools import lru_cache

from dataverse.config import get_settings
from dataverse.storage.base import StorageBackend
from dataverse.storage.local import LocalStorage


@lru_cache
def get_storage() -> StorageBackend:
    settings = get_settings()
    if settings.storage_backend == "local":
        return LocalStorage(settings.storage_path)
    msg = f"storage backend not implemented: {settings.storage_backend}"
    raise NotImplementedError(msg)


__all__ = ["LocalStorage", "StorageBackend", "get_storage"]
