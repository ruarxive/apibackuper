import os
import sqlite3
from typing import List, Optional
from zipfile import ZipFile, ZIP_DEFLATED


class StorageBackend:
    """Abstract storage backend."""

    def save_page(self, name: str, content: bytes) -> None:
        raise NotImplementedError

    def save_object(self, name: str, content: bytes) -> None:
        raise NotImplementedError

    def list_objects(self, kind: str = "page") -> List[str]:
        raise NotImplementedError

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        raise NotImplementedError

    def close(self) -> None:
        pass


class ZipStorageBackend(StorageBackend):
    """ZIP storage backend implementation."""

    def __init__(self, filename: str, mode: str = "a", compression=ZIP_DEFLATED) -> None:
        self._zip = ZipFile(filename, mode=mode, compression=compression)
        self._names = set(self._zip.namelist())

    def save_page(self, name: str, content: bytes) -> None:
        self._zip.writestr(name, content)
        self._names.add(name)

    def save_object(self, name: str, content: bytes) -> None:
        self._zip.writestr(name, content)
        self._names.add(name)

    def list_objects(self, kind: str = "page") -> List[str]:
        if kind == "page":
            return sorted([name for name in self._names if name.startswith("page_")])
        return sorted(self._names)

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        if name not in self._names:
            return None
        with self._zip.open(name, "r") as handle:
            return handle.read()

    def close(self) -> None:
        self._zip.close()


class SqliteStorageBackend(StorageBackend):
    """SQLite storage backend implementation."""

    def __init__(self, filename: str, reset: bool = False) -> None:
        self._conn = sqlite3.connect(filename)
        self._ensure_tables(reset=reset)

    def _ensure_tables(self, reset: bool = False) -> None:
        cursor = self._conn.cursor()
        if reset:
            cursor.execute("DROP TABLE IF EXISTS pages")
            cursor.execute("DROP TABLE IF EXISTS objects")
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS pages (name TEXT PRIMARY KEY, content BLOB, created_at TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS objects (name TEXT PRIMARY KEY, content BLOB, created_at TEXT)"
        )
        self._conn.commit()

    def save_page(self, name: str, content: bytes) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO pages (name, content, created_at) VALUES (?, ?, datetime('now'))",
            (name, sqlite3.Binary(content)),
        )
        self._conn.commit()

    def save_object(self, name: str, content: bytes) -> None:
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO objects (name, content, created_at) VALUES (?, ?, datetime('now'))",
            (name, sqlite3.Binary(content)),
        )
        self._conn.commit()

    _ALLOWED_TABLES = {"pages", "objects"}

    def _table_name(self, kind: str) -> str:
        """Resolve kind to a validated table name."""
        if kind not in ("page", "object"):
            raise ValueError(f"Invalid table kind: {kind}")
        return "pages" if kind == "page" else "objects"

    def list_objects(self, kind: str = "page") -> List[str]:
        table = self._table_name(kind)
        cursor = self._conn.cursor()
        cursor.execute(f"SELECT name FROM {table} ORDER BY name")
        return [row[0] for row in cursor.fetchall()]

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        table = self._table_name(kind)
        cursor = self._conn.cursor()
        cursor.execute(f"SELECT content FROM {table} WHERE name = ?", (name,))
        row = cursor.fetchone()
        if not row:
            return None
        return row[0]

    def close(self) -> None:
        self._conn.close()


def build_storage_backend(storage_type: str, storage_path: str, mode: str) -> StorageBackend:
    if storage_type == "zip":
        zip_mode = "w" if mode == "full" else "a"
        return ZipStorageBackend(storage_path, mode=zip_mode)
    if storage_type == "sqlite":
        reset = mode == "full"
        return SqliteStorageBackend(storage_path, reset=reset)
    raise ValueError(f"Unsupported storage type: {storage_type}")

