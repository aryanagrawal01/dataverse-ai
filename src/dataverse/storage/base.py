"""Storage backend protocol.

Dataset artifacts (Parquet files, PDFs) live behind this interface — the app
never touches the filesystem or S3 directly.
"""

from typing import Protocol


class StorageBackend(Protocol):
    def put(self, key: str, data: bytes) -> None:
        """Store bytes under key, overwriting if present."""
        ...

    def get(self, key: str) -> bytes:
        """Return stored bytes. Raises StorageError if missing."""
        ...

    def delete(self, key: str) -> None:
        """Delete if present; missing keys are a no-op."""
        ...

    def exists(self, key: str) -> bool: ...

    def size_bytes(self, key: str) -> int:
        """Size of stored object. Raises StorageError if missing."""
        ...
