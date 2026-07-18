import pytest

from dataverse.storage.local import LocalStorage
from dataverse.utils.errors import StorageError


@pytest.fixture
def storage(tmp_path):
    return LocalStorage(tmp_path / "artifacts")


def test_put_get_roundtrip(storage):
    storage.put("u1/p1/raw.parquet", b"hello")
    assert storage.get("u1/p1/raw.parquet") == b"hello"
    assert storage.exists("u1/p1/raw.parquet")
    assert storage.size_bytes("u1/p1/raw.parquet") == 5


def test_put_overwrites(storage):
    storage.put("k", b"one")
    storage.put("k", b"two")
    assert storage.get("k") == b"two"


def test_get_missing_raises(storage):
    with pytest.raises(StorageError):
        storage.get("nope")
    with pytest.raises(StorageError):
        storage.size_bytes("nope")


def test_delete_is_idempotent(storage):
    storage.put("k", b"x")
    storage.delete("k")
    assert not storage.exists("k")
    storage.delete("k")  # no error


def test_path_traversal_blocked(storage):
    with pytest.raises(StorageError):
        storage.put("../../escape.txt", b"evil")
