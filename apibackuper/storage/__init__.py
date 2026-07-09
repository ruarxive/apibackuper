from zipfile import ZipFile, ZIP_DEFLATED
import os

from .backends import (
    StorageBackend,
    ZipStorageBackend,
    SqliteStorageBackend,
    build_storage_backend,
)


class FileStorage:
    """Base file storage class"""

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

    def __init__(self, filename, mode="a", compression=ZIP_DEFLATED):
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

    def __init__(self, dirpath=os.path.join("storage", "files")):
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
