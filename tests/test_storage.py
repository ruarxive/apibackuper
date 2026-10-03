"""Tests for storage classes"""
import os
import tempfile
import zipfile
import pytest
from apibackuper.storage import (
    FileStorage,
    FilesystemStorageBackend,
    ZipStorageBackend,
    SqliteStorageBackend,
    build_storage_backend,
)


class TestFileStorage:
    """Tests for base FileStorage class"""
    
    def test_exists_not_implemented(self):
        """Test that exists raises NotImplementedError"""
        storage = FileStorage()
        with pytest.raises(NotImplementedError):
            storage.exists("test")
    
    def test_store_not_implemented(self):
        """Test that store raises NotImplementedError"""
        storage = FileStorage()
        with pytest.raises(NotImplementedError):
            storage.store("test", b"content")
    
    def test_close_no_op(self):
        """Test that close does nothing by default"""
        storage = FileStorage()
        # Should not raise
        storage.close()


class TestZipStorageBackendMigration:
    """Migration of the legacy TestZipFileStorage scenarios to the
    new ``ZipStorageBackend`` Protocol implementation. Same coverage,
    new API (``save_object`` / ``list_objects`` / ``get_object``)."""

    def test_init_create_new(self, temp_dir):
        """Creating a new zip backend writes an empty archive."""
        zip_path = os.path.join(temp_dir, "test.zip")
        backend = ZipStorageBackend(zip_path, mode="w")
        assert os.path.exists(zip_path)
        backend.close()

    def test_store_and_retrieve_file(self, temp_dir):
        """Round-trip via ``save_object`` + ``get_object``."""
        zip_path = os.path.join(temp_dir, "test.zip")
        backend = ZipStorageBackend(zip_path, mode="w")
        backend.save_object("test.txt", b"test content")
        backend.close()

        # Verify via raw zipfile
        with zipfile.ZipFile(zip_path, 'r') as zf:
            assert "test.txt" in zf.namelist()
            assert zf.read("test.txt") == b"test content"

    def test_list_objects_contains_saved(self, temp_dir):
        """``list_objects("object")`` reflects what was saved."""
        zip_path = os.path.join(temp_dir, "test.zip")
        backend = ZipStorageBackend(zip_path, mode="w")
        backend.save_object("test.txt", b"test content")
        assert "test.txt" in backend.list_objects("object")
        assert "nonexistent.txt" not in backend.list_objects("object")
        backend.close()

    def test_store_multiple_files(self, temp_dir):
        """Multiple objects stored + all retrievable."""
        zip_path = os.path.join(temp_dir, "test.zip")
        backend = ZipStorageBackend(zip_path, mode="w")
        backend.save_object("file1.txt", b"content1")
        backend.save_object("file2.txt", b"content2")
        backend.save_object("subdir/file3.txt", b"content3")
        backend.close()

        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "file1.txt" in files
            assert "file2.txt" in files
            assert "subdir/file3.txt" in files

    def test_append_mode(self, temp_dir):
        """Appending to an existing archive preserves prior entries."""
        zip_path = os.path.join(temp_dir, "test.zip")

        # Initial write
        backend1 = ZipStorageBackend(zip_path, mode="w")
        backend1.save_object("file1.txt", b"content1")
        backend1.close()

        # Re-open in append mode
        backend2 = ZipStorageBackend(zip_path, mode="a")
        backend2.save_object("file2.txt", b"content2")
        backend2.close()

        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "file1.txt" in files
            assert "file2.txt" in files


class TestFilesystemStorageBackendMigration:
    """Migration of legacy TestFilesystemStorage scenarios to the
    new ``FilesystemStorageBackend`` Protocol implementation."""

    def test_init_default_path(self, temp_dir):
        """Default root dir is the supplied cwd-relative default."""
        with tempfile.TemporaryDirectory() as isolated:
            original = os.getcwd()
            try:
                os.chdir(isolated)
                backend = FilesystemStorageBackend("storage/files")
                assert backend._root == os.path.abspath("storage/files")
                backend.close()
            finally:
                os.chdir(original)

    def test_init_custom_path(self, temp_dir):
        """Custom root path is honoured."""
        custom_path = os.path.join(temp_dir, "custom_storage")
        backend = FilesystemStorageBackend(custom_path, mode="a")
        assert backend._root == os.path.abspath(custom_path)
        backend.close()

    def test_store_and_retrieve_file(self, temp_dir):
        """Round-trip via ``save_object`` + ``get_object``."""
        storage_path = os.path.join(temp_dir, "storage")
        backend = FilesystemStorageBackend(storage_path, mode="a")
        backend.save_object("test.txt", b"test content")
        assert backend.get_object("test.txt", "object") == b"test content"
        backend.close()

    def test_store_nested_file(self, temp_dir):
        """Sub-directory names create nested paths automatically."""
        storage_path = os.path.join(temp_dir, "storage")
        backend = FilesystemStorageBackend(storage_path, mode="a")
        backend.save_object("subdir/nested.txt", b"nested content")
        # The on-disk path keeps the original directory structure
        # (the ``object_`` prefix is only used in the index for
        # disambiguation, not in the filename itself).
        assert os.path.exists(os.path.join(storage_path, "subdir", "nested.txt"))
        assert backend.get_object("subdir/nested.txt", "object") == b"nested content"
        backend.close()

    def test_list_objects_contains_saved(self, temp_dir):
        """``list_objects("object")`` reflects what was saved."""
        storage_path = os.path.join(temp_dir, "storage")
        backend = FilesystemStorageBackend(storage_path, mode="a")
        backend.save_object("test.txt", b"test content")
        assert "test.txt" in backend.list_objects("object")
        assert "nonexistent.txt" not in backend.list_objects("object")
        backend.close()

    def test_store_strips_leading_slashes(self, temp_dir):
        """Leading slashes are stripped by the safe-path helper so the
        written file has no leading separator, even though the index
        preserves the original (escaped) name."""
        storage_path = os.path.join(temp_dir, "storage")
        backend = FilesystemStorageBackend(storage_path, mode="a")
        backend.save_object("/test.txt", b"content")
        backend.save_object("\\test2.txt", b"content2")
        # The on-disk filename has the leading slash stripped.
        assert os.path.exists(os.path.join(storage_path, "test.txt"))
        assert os.path.exists(os.path.join(storage_path, "test2.txt"))
        backend.close()

    def test_store_multiple_files(self, temp_dir):
        """Multiple objects round-trip correctly."""
        storage_path = os.path.join(temp_dir, "storage")
        backend = FilesystemStorageBackend(storage_path, mode="a")
        backend.save_object("file1.txt", b"content1")
        backend.save_object("file2.txt", b"content2")
        backend.save_object("subdir/file3.txt", b"content3")
        assert backend.get_object("file1.txt", "object") == b"content1"
        assert backend.get_object("file2.txt", "object") == b"content2"
        assert backend.get_object("subdir/file3.txt", "object") == b"content3"
        backend.close()


class TestStorageBackends:
    """Tests for new storage backends"""

    def test_zip_backend_save_and_get(self, temp_dir):
        zip_path = os.path.join(temp_dir, "pages.zip")
        backend = ZipStorageBackend(zip_path, mode="w")
        backend.save_page("page_1.json", b'{"items": []}')
        backend.save_object("obj_1.json", b'{"id": 1}')
        backend.close()

        backend = ZipStorageBackend(zip_path, mode="a")
        assert "page_1.json" in backend.list_objects("page")
        assert backend.get_object("page_1.json") == b'{"items": []}'
        backend.close()

    def test_sqlite_backend_save_and_get(self, temp_dir):
        db_path = os.path.join(temp_dir, "storage.db")
        backend = SqliteStorageBackend(db_path, reset=True)
        backend.save_page("page_1.json", b'{"items": []}')
        backend.save_object("obj_1.json", b'{"id": 1}')
        backend.close()

        backend = SqliteStorageBackend(db_path)
        assert "page_1.json" in backend.list_objects("page")
        assert "obj_1.json" in backend.list_objects("object")
        assert backend.get_object("page_1.json", "page") == b'{"items": []}'
        backend.close()

    def test_build_storage_backend(self, temp_dir):
        zip_path = os.path.join(temp_dir, "storage.zip")
        sqlite_path = os.path.join(temp_dir, "storage.db")
        zip_backend = build_storage_backend("zip", zip_path, "full")
        sqlite_backend = build_storage_backend("sqlite", sqlite_path, "full")
        assert isinstance(zip_backend, ZipStorageBackend)
        assert isinstance(sqlite_backend, SqliteStorageBackend)
        zip_backend.close()
        sqlite_backend.close()


class TestFilesystemStorageSecurity:
    """Tests for FilesystemStorage path traversal prevention"""

    def test_path_traversal_rejected(self, temp_dir):
        """Test that path traversal attempts are rejected"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorageBackend(storage_path, mode="a")

        with pytest.raises(ValueError, match="Path traversal"):
            storage.save_object("../../etc/passwd", b"malicious")

    def test_normal_nested_path_accepted(self, temp_dir):
        """Test that normal nested paths work correctly"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorageBackend(storage_path, mode="a")
        storage.save_object("subdir/deep/file.txt", b"content")

        assert "subdir/deep/file.txt" in storage.list_objects("object")
        file_path = os.path.join(storage_path, "subdir", "deep", "file.txt")
        assert os.path.exists(file_path)


class TestSqliteStorageBackendSecurity:
    """Tests for SQL injection prevention"""

    def test_invalid_table_name_rejected(self, temp_dir):
        """Test that invalid table names raise ValueError"""
        db_path = os.path.join(temp_dir, "storage.db")
        backend = SqliteStorageBackend(db_path, reset=True)
        backend.save_page("page_1.json", b"test")

        with pytest.raises(ValueError, match="Invalid table"):
            backend.list_objects("nonexistent")

        backend.close()

    def test_valid_table_names_work(self, temp_dir):
        """Test that valid table names work correctly"""
        db_path = os.path.join(temp_dir, "storage.db")
        backend = SqliteStorageBackend(db_path, reset=True)
        backend.save_page("page_1.json", b"test")
        backend.save_object("obj_1.json", b"test")

        pages = backend.list_objects("page")
        objects = backend.list_objects("object")
        assert "page_1.json" in pages
        assert "obj_1.json" in objects

        backend.close()


class TestStorageEdgeCases:
    """Storage must handle empty and binary payloads without crashing.

    These cover the edge cases called out in §3.8-3.9 of the
    ``improve-test-quality`` backlog (2026-10 analysis report).
    """

    def test_filesystem_empty_content(self, temp_dir):
        """Storing an empty byte string round-trips correctly."""
        backend = build_storage_backend("filesystem", temp_dir, "w")
        backend.save_object("empty.json", b"")
        assert "empty.json" in backend.list_objects("object")
        assert backend.get_object("empty.json", "object") == b""

    def test_zip_empty_content(self, temp_dir):
        """Zip backend round-trips empty bytes."""
        backend = build_storage_backend(
            "zip", os.path.join(temp_dir, "store.zip"), "w"
        )
        backend.save_object("empty.json", b"")
        assert "empty.json" in backend.list_objects("object")
        assert backend.get_object("empty.json", "object") == b""

    def test_filesystem_binary_content(self, temp_dir):
        """Non-UTF-8 binary content round-trips intact."""
        backend = build_storage_backend("filesystem", temp_dir, "w")
        # PNG header bytes — definitely not UTF-8.
        payload = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        backend.save_object("blob.bin", payload)
        assert backend.get_object("blob.bin", "object") == payload

    def test_zip_binary_content(self, temp_dir):
        """Zip backend round-trips binary content."""
        backend = build_storage_backend(
            "zip", os.path.join(temp_dir, "store.zip"), "w"
        )
        payload = bytes(range(256))  # full byte range
        backend.save_object("blob.bin", payload)
        assert backend.get_object("blob.bin", "object") == payload

    def test_sqlite_binary_content(self, temp_dir):
        """SQLite backend round-trips binary content."""
        backend = build_storage_backend(
            "sqlite", os.path.join(temp_dir, "store.db"), "w"
        )
        payload = b"\x00\x01\x02\xff\xfe\xfd"
        backend.save_object("blob.bin", payload)
        assert backend.get_object("blob.bin", "object") == payload


class TestLegacyStorageDeprecation:
    """Legacy ``FileStorage`` subclasses (ZipFileStorage, FilesystemStorage)
    are deprecated in favour of the ``StorageBackend`` Protocol. Using them
    emits a DeprecationWarning pointing at the new class. New code must
    not instantiate the legacy classes — these tests pin the warning
    contract so consumers see the migration hint."""

    def test_zip_file_storage_emits_deprecation(self, tmp_path):
        import warnings as warnings
        from apibackuper.storage import ZipFileStorage
        zip_path = os.path.join(str(tmp_path), "store.zip")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            ZipFileStorage(zip_path, mode="w")
            deprecation_warnings = [
                w for w in caught if issubclass(w.category, DeprecationWarning)
            ]
        assert len(deprecation_warnings) >= 1
        assert "ZipFileStorage" in str(deprecation_warnings[0].message)
        assert "ZipStorageBackend" in str(deprecation_warnings[0].message)

    def test_filesystem_storage_emits_deprecation(self, tmp_path):
        import warnings as warnings
        from apibackuper.storage import FilesystemStorage
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            FilesystemStorage(os.path.join(str(tmp_path), "files"))
            deprecation_warnings = [
                w for w in caught if issubclass(w.category, DeprecationWarning)
            ]
        assert len(deprecation_warnings) >= 1
        assert "FilesystemStorage" in str(deprecation_warnings[0].message)
        assert "FilesystemStorageBackend" in str(deprecation_warnings[0].message)

    def test_importing_legacy_classes_is_silent(self):
        # Just importing should NOT emit the deprecation warning —
        # the warning is reserved for actual instantiation.
        import warnings as warnings
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            from apibackuper.storage import ZipFileStorage, FilesystemStorage  # noqa
            deprecation_warnings = [
                w for w in caught if issubclass(w.category, DeprecationWarning)
            ]
        # No deprecation warnings on import alone.
        assert deprecation_warnings == []

