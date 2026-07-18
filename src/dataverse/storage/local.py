"""Local-filesystem storage backend (dev / single-node deployments).

Keys are always server-generated (uuid-based) — never user filenames — so no
path traversal is possible; guarded anyway as defense in depth.
"""

from pathlib import Path

from dataverse.utils.errors import StorageError


class LocalStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self._root / key).resolve()
        if not p.is_relative_to(self._root):
            raise StorageError(f"key escapes storage root: {key!r}")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)  # atomic on same filesystem

    def get(self, key: str) -> bytes:
        p = self._path(key)
        if not p.is_file():
            raise StorageError(f"missing storage key: {key}")
        return p.read_bytes()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.is_file():
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def size_bytes(self, key: str) -> int:
        p = self._path(key)
        if not p.is_file():
            raise StorageError(f"missing storage key: {key}")
        return p.stat().st_size
