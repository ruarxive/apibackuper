"""Unified storage backends.

All storage backends live in :mod:`apibackuper.storage.backends` as the
canonical implementation. This package-level module re-exports the public
API so callers can write ``from apibackuper.storage import ...``.

Two storage *flavours* are exposed:

- ``StorageBackend`` (Protocol) and its concrete implementations
  (``ZipStorageBackend``, ``SqliteStorageBackend``, ``FilesystemStorageBackend``)
  are used by the main backup flow (``ProjectBuilder.run``).

- ``FileStorage`` (legacy) and its concrete implementations
  (``ZipFileStorage``, ``FilesystemStorage``) are used by the
  ``getfiles`` flow which predates the unified Protocol.

Both flavours are exported here so callers see one import surface.
"""
import os
from zipfile import ZipFile, ZIP_DEFLATED
import warnings

from .backends import (
    StorageBackend,
    ZipStorageBackend,
    SqliteStorageBackend,
    FilesystemStorageBackend,
    build_storage_backend,
    safe_member_name,
)


def _deprecate_legacy(legacy_name: str, replacement: str) -> None:
    """Emit a DeprecationWarning when a legacy storage class is instantiated.

    Called from each legacy class's ``__init__`` so importing is silent
    but using the class produces a one-shot warning pointing users at
    the new ``StorageBackend`` Protocol implementation.
    """
    warnings.warn(
        f"{legacy_name} is deprecated; use {replacement} from "
        f"apibackuper.storage.backends instead. See the unify-storage-layer "
        f"OpenSpec change for the migration path.",
        DeprecationWarning,
        stacklevel=3,
    )


class FileStorage:
    """Base class for the legacy ``getfiles``-flow file storage.

    New code should prefer :class:`StorageBackend` directly.
    """

    def __init__(self):
        """Initialize base file storage"""

    def exists(self, name):
        raise NotImplementedError

    def store(self, filename, content):
        raise NotImplementedError

    def close(self):
        """Default implementation. Don't do anything"""
        pass


class ZipFileStorage(FileStorage):
    """Zip-based storage used by the ``getfiles`` flow.

    Stores files into a single ``.zip`` archive. The newer
    :class:`ZipStorageBackend` implements the same idea under the unified
    :class:`StorageBackend` Protocol — when writing new code prefer that
    class.
    """

    def __init__(self, filename, mode="a", compression=ZIP_DEFLATED):
        _deprecate_legacy("ZipFileStorage", "ZipStorageBackend")
        FileStorage.__init__(self)
        self.mzip = ZipFile(filename, mode=mode, compression=compression)
        self.allfiles = self.mzip.namelist()

    def store(self, filename, content):
        self.mzip.writestr(filename, content)
        self.allfiles.append(filename)

    def exists(self, filename):
        if filename in self.allfiles:
            return True
        return False

    def close(self):
        self.mzip.close()


class FilesystemStorage(FileStorage):
    """Filesystem-based storage used by the ``getfiles`` flow.

    Writes files into a directory tree under ``dirpath``. Path traversal
    is rejected via :meth:`_safe_path`. New code should prefer
    :class:`FilesystemStorageBackend`.
    """

    def __init__(self, dirpath=os.path.join("storage", "files")):
        _deprecate_legacy("FilesystemStorage", "FilesystemStorageBackend")
        FileStorage.__init__(self)
        self.dirpath = dirpath

    def _safe_path(self, filename):
        """Resolve filename to a path inside dirpath, rejecting traversal attempts."""
        # Strip leading slashes and backslashes
        clean = filename.lstrip('/').lstrip('\\')
        base = os.path.abspath(self.dirpath)
        fullname = os.path.abspath(os.path.join(base, clean))
        # Reject paths that escape the base directory
        if not fullname.startswith(base + os.sep) and fullname != base:
            raise ValueError(f"Path traversal detected: {filename}")
        return fullname

    def exists(self, filename):
        fullname = self._safe_path(filename)
        return os.path.exists(fullname)

    def store(self, filename, content):
        fullname = self._safe_path(filename)
        os.makedirs(os.path.dirname(fullname), exist_ok=True)
        with open(fullname, "wb") as fobj:
            fobj.write(content)


__all__ = [
    "StorageBackend",
    "ZipStorageBackend",
    "SqliteStorageBackend",
    "FilesystemStorageBackend",
    "build_storage_backend",
    "safe_member_name",
    "FileStorage",
    "ZipFileStorage",
    "FilesystemStorage",
]
