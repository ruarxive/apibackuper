import io
import os
import re
import shutil
import sqlite3
import tempfile
from typing import IO, List, Optional
from zipfile import ZIP_DEFLATED, ZipFile


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

    def flush(self) -> None:
        """Make saved pages durable before advancing a checkpoint."""

    def save_object_from_path(self, name: str, path: str) -> None:
        """Store the complete file at ``path`` as object ``name`` and remove it.

        Backends that can move the file into place override this to avoid
        reading it into memory.
        """
        with open(path, "rb") as handle:
            self.save_object(name, handle.read())
        os.unlink(path)

    def open_object(self, name: str) -> Optional[IO[bytes]]:
        """Open object ``name`` for reading, or return None if it is absent."""
        content = self.get_object(name, "object")
        return None if content is None else io.BytesIO(content)


def _is_page(name: str) -> bool:
    return name.rsplit("/", 1)[-1].startswith("page_")


class _ZipArchive(StorageBackend):
    """One ZIP with a durable per-member journal and atomic archive publication.

    Appending directly can destroy the central directory on process termination.
    Journal pages remain readable after a crash; close compacts them once into a
    replacement ZIP, preserving the previous ZIP until the replacement is ready.
    """

    def __init__(self, filename: str, mode: str = "a", compression=ZIP_DEFLATED) -> None:
        self._filename = filename
        self._mode = mode
        self._compression = compression
        self._journal = filename + ".journal"
        self._closed = False
        if mode == "w":
            if os.path.isdir(self._journal):
                shutil.rmtree(self._journal)
            with ZipFile(filename, "w", compression=compression):
                pass
        elif mode != "r" and not os.path.exists(filename):
            with ZipFile(filename, "w", compression=compression):
                pass
        self._zip = ZipFile(filename, "r")
        self._names = set(self._zip.namelist())
        self._pending = set()
        # Journal directories whose entries changed since the last flush.
        self._dirty = set()
        if os.path.isdir(self._journal):
            for directory, _, files in os.walk(self._journal):
                self._dirty.add(directory)
                for entry in files:
                    if entry.endswith(".pending"):
                        name = os.path.relpath(os.path.join(directory, entry), self._journal)[:-8]
                        self._pending.add(name.replace(os.sep, "/"))
            self._names.update(self._pending)

    def save_page(self, name: str, content: bytes) -> None:
        self.save_object(name, content)

    def save_object(self, name: str, content: bytes) -> None:
        if self._mode == "r" or self._closed:
            raise ValueError("Storage is not open for writing")
        name = safe_member_name(name)
        destination = os.path.join(self._journal, name + ".pending")
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(destination))
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self._mark_pending(name, destination)

    def save_object_from_path(self, name: str, path: str) -> None:
        """Move a complete, fsynced file into the journal as member ``name``."""
        if self._mode == "r" or self._closed:
            raise ValueError("Storage is not open for writing")
        name = safe_member_name(name)
        destination = os.path.join(self._journal, name + ".pending")
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        os.replace(path, destination)
        self._mark_pending(name, destination)

    def _mark_pending(self, name: str, destination: str) -> None:
        self._pending.add(name)
        self._names.add(name)
        directory = os.path.dirname(destination)
        while directory.startswith(self._journal):
            self._dirty.add(directory)
            directory = os.path.dirname(directory)

    def open_object(self, name: str) -> Optional[IO[bytes]]:
        if name not in self._names:
            return None
        if name in self._pending:
            return open(os.path.join(self._journal, name + ".pending"), "rb")
        return self._zip.open(name, "r")

    def list_objects(self, kind: str = "page") -> List[str]:
        return sorted(name for name in self._names if kind != "page" or _is_page(name))

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        if name not in self._names:
            return None
        if name in self._pending:
            with open(os.path.join(self._journal, name + ".pending"), "rb") as handle:
                return handle.read()
        with self._zip.open(name, "r") as handle:
            return handle.read()

    def close(self) -> None:
        if self._closed:
            return
        if self._mode != "r" and self._pending:
            fd, temporary = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self._filename)))
            os.close(fd)
            try:
                with ZipFile(temporary, "w", compression=self._compression) as target:
                    for name in sorted(self._names):
                        if name in self._pending:
                            with (
                                open(
                                    os.path.join(self._journal, name + ".pending"), "rb"
                                ) as reader,
                                target.open(name, "w") as writer,
                            ):
                                shutil.copyfileobj(reader, writer)
                        else:
                            with self._zip.open(name) as reader, target.open(name, "w") as writer:
                                shutil.copyfileobj(reader, writer)
                with open(temporary, "rb") as handle:
                    os.fsync(handle.fileno())
                self._zip.close()
                os.replace(temporary, self._filename)
                shutil.rmtree(self._journal)
                self._pending.clear()
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
                if self._zip.fp is None and not self._closed:
                    self._zip = ZipFile(self._filename, "r")
        self._zip.close()
        self._closed = True

    def flush(self) -> None:
        # Each journal file was fsynced before its atomic rename. Preserve the
        # original ZIP central directory until close's atomic replacement.
        # Only directories touched since the last flush are synced, so
        # per-page checkpoints do not rescan the whole journal.
        if self._mode != "r" and os.path.isdir(self._journal):
            if os.name == "nt":
                return
            for directory in sorted(self._dirty):
                if not os.path.isdir(directory):
                    continue
                descriptor = os.open(directory, os.O_RDONLY)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
            self._dirty.clear()


# Update generation IDs, as validated by the backup session.
_RUN_ID = re.compile(r"[A-Za-z0-9_-]+")


class ZipStorageBackend(StorageBackend):
    """ZIP storage with one archive per update generation.

    Members named ``runs/<id>/...`` live in ``<archive>.runs/<id>.zip``, so an
    update compacts only its own small archive instead of rewriting the whole
    backup. All archives are listed and read as one set of names; generations
    stored inside the main archive by earlier versions stay readable, and a
    generation archive wins when both hold a name.
    """

    def __init__(self, filename: str, mode: str = "a", compression=ZIP_DEFLATED) -> None:
        self._filename = filename
        self._mode = mode
        self._compression = compression
        self._runs_dir = filename + ".runs"
        if mode == "w" and os.path.isdir(self._runs_dir):
            shutil.rmtree(self._runs_dir)
        self._base = _ZipArchive(filename, mode, compression)
        self._generations: dict = {}
        if os.path.isdir(self._runs_dir):
            for entry in sorted(os.listdir(self._runs_dir)):
                run_id = entry[: -len(".zip")]
                if entry.endswith(".zip") and _RUN_ID.fullmatch(run_id):
                    self._generations[run_id] = _ZipArchive(
                        os.path.join(self._runs_dir, entry),
                        "r" if mode == "r" else "a",
                        compression,
                    )

    @staticmethod
    def _generation_id(name: str) -> Optional[str]:
        parts = name.split("/", 2)
        if len(parts) == 3 and parts[0] == "runs" and _RUN_ID.fullmatch(parts[1]):
            return parts[1]
        return None

    def _writer(self, name: str) -> _ZipArchive:
        run_id = self._generation_id(name)
        if run_id is None:
            return self._base
        archive = self._generations.get(run_id)
        if archive is None:
            if self._mode == "r":
                raise ValueError("Storage is not open for writing")
            os.makedirs(self._runs_dir, exist_ok=True)
            archive = _ZipArchive(
                os.path.join(self._runs_dir, run_id + ".zip"), "a", self._compression
            )
            self._generations[run_id] = archive
        return archive

    def save_page(self, name: str, content: bytes) -> None:
        self.save_object(name, content)

    def save_object(self, name: str, content: bytes) -> None:
        name = safe_member_name(name)
        self._writer(name).save_object(name, content)

    def list_objects(self, kind: str = "page") -> List[str]:
        names = set(self._base.list_objects(kind))
        for archive in self._generations.values():
            names.update(archive.list_objects(kind))
        return sorted(names)

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        run_id = self._generation_id(name)
        archive = self._generations.get(run_id) if run_id else None
        if archive is not None:
            content = archive.get_object(name, kind)
            if content is not None:
                return content
        return self._base.get_object(name, kind)

    def save_object_from_path(self, name: str, path: str) -> None:
        name = safe_member_name(name)
        self._writer(name).save_object_from_path(name, path)

    def open_object(self, name: str) -> Optional[IO[bytes]]:
        run_id = self._generation_id(name)
        archive = self._generations.get(run_id) if run_id else None
        if archive is not None:
            handle = archive.open_object(name)
            if handle is not None:
                return handle
        return self._base.open_object(name)

    def generation_archives(self) -> List[str]:
        """Paths of the per-generation archives, sorted by run ID."""
        return [self._generations[run_id]._filename for run_id in sorted(self._generations)]

    def flush(self) -> None:
        for archive in self._generations.values():
            archive.flush()
        self._base.flush()

    def close(self) -> None:
        try:
            for archive in self._generations.values():
                archive.close()
        finally:
            self._base.close()


def publish_zip(staging: str, destination: str) -> None:
    """Keep old journal data recoverable without overlaying the replacement ZIP."""
    if os.path.isdir(destination + ".journal") and os.path.exists(destination):
        previous = ZipStorageBackend(destination)
        previous.close()
    os.replace(staging, destination)


class SqliteStorageBackend(StorageBackend):
    """SQLite storage backend implementation."""

    def __init__(self, filename: str, reset: bool = False, read_only: bool = False) -> None:
        if read_only:
            from pathlib import Path

            self._conn = sqlite3.connect(Path(filename).resolve().as_uri() + "?mode=ro", uri=True)
        else:
            self._conn = sqlite3.connect(filename)
            self._ensure_tables(reset=reset)
        self._closed = False

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
        # ``table`` is the result of ``_table_name`` which restricts the
        # value to {"pages", "objects"}; not user-controllable.
        cursor.execute(f"SELECT name FROM {table} ORDER BY name")  # nosec B608
        return [row[0] for row in cursor.fetchall()]

    def get_object(self, name: str, kind: str = "page") -> Optional[bytes]:
        table = self._table_name(kind)
        cursor = self._conn.cursor()
        # ``table`` is the result of ``_table_name`` which restricts the
        # value to {"pages", "objects"}; not user-controllable.
        cursor.execute(f"SELECT content FROM {table} WHERE name = ?", (name,))  # nosec B608
        row = cursor.fetchone()
        if not row:
            return None
        return row[0]

    def close(self) -> None:
        if not self._closed:
            self._conn.close()
            self._closed = True


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
        if mode == "read" and not os.path.isdir(self._root):
            raise FileNotFoundError(self._root)
        os.makedirs(self._root, exist_ok=True)
        self._index: dict[str, set[str]] = {self._PAGE_PREFIX: set(), self._OBJECT_PREFIX: set()}
        # Pre-populate from existing files so list_objects works after restart.
        if os.path.isdir(self._root):
            for directory, _, files in os.walk(self._root):
                for entry in files:
                    name = os.path.relpath(os.path.join(directory, entry), self._root).replace(
                        os.sep, "/"
                    )
                    prefix = self._PAGE_PREFIX if _is_page(name) else self._OBJECT_PREFIX
                    self._index[prefix].add(name)

    def _safe_path(self, name: str) -> str:
        """Resolve name to a path inside ``root``, rejecting traversal attempts."""
        clean = name.lstrip("/").lstrip("\\")
        fullname = os.path.realpath(os.path.join(self._root, clean))
        root = os.path.realpath(self._root)
        if not fullname.startswith(root + os.sep) and fullname != root:
            raise ValueError(f"Path traversal detected: {name}")
        return fullname

    def _save(self, prefix: str, name: str, content: bytes) -> None:
        fullname = self._safe_path(name)
        os.makedirs(os.path.dirname(fullname), exist_ok=True)
        fd, temporary = tempfile.mkstemp(dir=os.path.dirname(fullname))
        try:
            with os.fdopen(fd, "wb") as fobj:
                fobj.write(content)
                fobj.flush()
                os.fsync(fobj.fileno())
            os.replace(temporary, fullname)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
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

    def save_object_from_path(self, name: str, path: str) -> None:
        fullname = self._safe_path(name)
        os.makedirs(os.path.dirname(fullname), exist_ok=True)
        os.replace(path, fullname)
        self._index[self._OBJECT_PREFIX].add(name)

    def open_object(self, name: str) -> Optional[IO[bytes]]:
        try:
            fullname = self._safe_path(name)
        except ValueError:
            return None
        return open(fullname, "rb") if os.path.exists(fullname) else None

    def close(self) -> None:
        # No persistent handle; nothing to flush.
        return None


def build_storage_backend(storage_type: str, storage_path: str, mode: str) -> StorageBackend:
    if storage_type == "zip":
        zip_mode = "w" if mode == "full" else "r" if mode == "read" else "a"
        return ZipStorageBackend(storage_path, mode=zip_mode)
    if storage_type == "sqlite":
        reset = mode == "full"
        return SqliteStorageBackend(storage_path, reset=reset, read_only=mode == "read")
    if storage_type == "filesystem":
        return FilesystemStorageBackend(storage_path, mode=mode)
    raise ValueError(f"Unsupported storage type: {storage_type}")
