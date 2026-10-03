import os
import posixpath
import re
import sqlite3
from typing import List, Optional
from zipfile import ZipFile, ZIP_DEFLATED


def safe_member_name(name: str) -> str:
    """Return a zip-member-safe version of ``name``.

    Replaces path separators and ``..`` segments with a single underscore so
    server-supplied or API-derived names cannot escape the archive via zip
    viewers or extraction tools (§5.2 of the 2026-10 analysis report).

    - Strips leading slashes and backslashes
    - Splits on both ``/`` and ``\\`` so the same defence works for ZIP and
      Windows-style paths
    - Collapses any ``..`` segment to ``_``
    - Replaces control characters and zero-width unicode
    """
    if name is None:
        raise ValueError("member name is None")
    cleaned = str(name).replace("\\", "/").lstrip("/")
    # Drop any null bytes / control characters early
    cleaned = re.sub(r"[\x00-\x1f\x7f\u200b-\u200f\ufeff]", "_", cleaned)
    # Split, drop empty parts and ".." segments, then re-join with "/".
    parts = []
    for part in cleaned.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            parts.append("_")
            continue
        parts.append(part)
    if not parts:
        raise ValueError(f"member name resolves to empty after sanitization: {name!r}")
    return "/".join(parts)


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
        # P2.22: central name sanitization (§5.2).
        safe_name = safe_member_name(name)
        self._zip.writestr(safe_name, content)
        self._names.add(safe_name)

    def save_object(self, name: str, content: bytes) -> None:
        safe_name = safe_member_name(name)
        self._zip.writestr(safe_name, content)
        self._names.add(safe_name)

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


class FilesystemStorageBackend(StorageBackend):
    """Filesystem storage backend.

    Stores pages and objects as individual files under ``root``. Schema-legal
    option ``storage.storage_type: "filesystem"`` previously raised
    ``ValueError`` from ``build_storage_backend`` (§4.6 of the 2026-10
    analysis report); this adapter makes it a working backend.

    A ``mode`` of ``"full"`` wipes the root directory before opening; other
    modes append to existing files.
    """

    _PAGE_PREFIX = "page_"
    _OBJECT_PREFIX = "object_"

    def __init__(self, root: str, mode: str = "a") -> None:
        import shutil

        self._root = os.path.abspath(root)
        if mode == "full" and os.path.isdir(self._root):
            shutil.rmtree(self._root)
        os.makedirs(self._root, exist_ok=True)
        self._index: dict[str, set[str]] = {self._PAGE_PREFIX: set(), self._OBJECT_PREFIX: set()}
        # Pre-populate from existing files so list_objects works after restart.
        if os.path.isdir(self._root):
            for entry in os.listdir(self._root):
                if entry.startswith(self._PAGE_PREFIX):
                    self._index[self._PAGE_PREFIX].add(entry)
                else:
                    self._index[self._OBJECT_PREFIX].add(entry)

    def _safe_path(self, name: str) -> str:
        """Resolve name to a path inside ``root``, rejecting traversal attempts."""
        clean = name.lstrip("/").lstrip("\\")
        fullname = os.path.abspath(os.path.join(self._root, clean))
        if not fullname.startswith(self._root + os.sep) and fullname != self._root:
            raise ValueError(f"Path traversal detected: {name}")
        return fullname

    def _save(self, prefix: str, name: str, content: bytes) -> None:
        fullname = self._safe_path(name)
        os.makedirs(os.path.dirname(fullname), exist_ok=True)
        with open(fullname, "wb") as fobj:
            fobj.write(content)
        self._index[prefix].add(name)

    def save_page(self, name: str, content: bytes) -> None:
        self._save(self._PAGE_PREFIX, name, content)

    def save_object(self, name: str, content: bytes) -> None:
        self._save(self._OBJECT_PREFIX, name, content)

    def list_objects(self, kind: str = "page") -> List[str]:
        prefix = self._PAGE_PREFIX if kind == "page" else self._OBJECT_PREFIX
        return sorted(self._index[prefix])

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        try:
            fullname = self._safe_path(name)
        except ValueError:
            return None
        if not os.path.exists(fullname):
            return None
        with open(fullname, "rb") as fobj:
            return fobj.read()

    def close(self) -> None:
        # No persistent handle; nothing to flush.
        return None


def build_storage_backend(storage_type: str, storage_path: str, mode: str) -> StorageBackend:
    if storage_type == "zip":
        zip_mode = "w" if mode == "full" else "a"
        return ZipStorageBackend(storage_path, mode=zip_mode)
    if storage_type == "sqlite":
        reset = mode == "full"
        return SqliteStorageBackend(storage_path, reset=reset)
    if storage_type == "filesystem":
        return FilesystemStorageBackend(storage_path, mode=mode)
    raise ValueError(f"Unsupported storage type: {storage_type}")

