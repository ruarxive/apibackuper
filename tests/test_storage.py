"""Tests for storage classes"""
import os
import tempfile
import zipfile
import pytest
from apibackuper.storage import FileStorage, ZipFileStorage, FilesystemStorage


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


class TestZipFileStorage:
    """Tests for ZipFileStorage class"""
    
    def test_init_create_new(self, temp_dir):
        """Test creating new zip file storage"""
        zip_path = os.path.join(temp_dir, "test.zip")
        storage = ZipFileStorage(zip_path)
        assert os.path.exists(zip_path)
        storage.close()
    
    def test_store_file(self, temp_dir):
        """Test storing file in zip"""
        zip_path = os.path.join(temp_dir, "test.zip")
        storage = ZipFileStorage(zip_path)
        storage.store("test.txt", b"test content")
        storage.close()
        
        # Verify file exists in zip
        with zipfile.ZipFile(zip_path, 'r') as zf:
            assert "test.txt" in zf.namelist()
            content = zf.read("test.txt")
            assert content == b"test content"
    
    def test_exists(self, temp_dir):
        """Test checking if file exists in zip"""
        zip_path = os.path.join(temp_dir, "test.zip")
        storage = ZipFileStorage(zip_path)
        storage.store("test.txt", b"test content")
        
        assert storage.exists("test.txt")
        assert not storage.exists("nonexistent.txt")
        storage.close()
    
    def test_store_multiple_files(self, temp_dir):
        """Test storing multiple files"""
        zip_path = os.path.join(temp_dir, "test.zip")
        storage = ZipFileStorage(zip_path)
        storage.store("file1.txt", b"content1")
        storage.store("file2.txt", b"content2")
        storage.store("subdir/file3.txt", b"content3")
        storage.close()
        
        # Verify all files exist
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "file1.txt" in files
            assert "file2.txt" in files
            assert "subdir/file3.txt" in files
    
    def test_append_mode(self, temp_dir):
        """Test appending to existing zip file"""
        zip_path = os.path.join(temp_dir, "test.zip")
        
        # Create initial zip
        storage1 = ZipFileStorage(zip_path)
        storage1.store("file1.txt", b"content1")
        storage1.close()
        
        # Append to it
        storage2 = ZipFileStorage(zip_path, mode="a")
        storage2.store("file2.txt", b"content2")
        storage2.close()
        
        # Verify both files exist
        with zipfile.ZipFile(zip_path, 'r') as zf:
            files = zf.namelist()
            assert "file1.txt" in files
            assert "file2.txt" in files


class TestFilesystemStorage:
    """Tests for FilesystemStorage class"""
    
    def test_init_default_path(self):
        """Test initializing with default path"""
        storage = FilesystemStorage()
        assert storage.dirpath == os.path.join("storage", "files")
    
    def test_init_custom_path(self, temp_dir):
        """Test initializing with custom path"""
        custom_path = os.path.join(temp_dir, "custom_storage")
        storage = FilesystemStorage(custom_path)
        assert storage.dirpath == custom_path
    
    def test_store_file(self, temp_dir):
        """Test storing file on filesystem"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorage(storage_path)
        storage.store("test.txt", b"test content")
        
        # Verify file exists
        file_path = os.path.join(storage_path, "test.txt")
        assert os.path.exists(file_path)
        with open(file_path, "rb") as f:
            assert f.read() == b"test content"
    
    def test_store_nested_file(self, temp_dir):
        """Test storing file in nested directory"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorage(storage_path)
        storage.store("subdir/nested.txt", b"nested content")
        
        # Verify file exists
        file_path = os.path.join(storage_path, "subdir", "nested.txt")
        assert os.path.exists(file_path)
        with open(file_path, "rb") as f:
            assert f.read() == b"nested content"
    
    def test_exists(self, temp_dir):
        """Test checking if file exists"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorage(storage_path)
        storage.store("test.txt", b"test content")
        
        assert storage.exists("test.txt")
        assert not storage.exists("nonexistent.txt")
    
    def test_store_strips_leading_slashes(self, temp_dir):
        """Test that leading slashes are stripped from filename"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorage(storage_path)
        storage.store("/test.txt", b"content")
        storage.store("\\test2.txt", b"content2")
        
        # Verify files exist without leading slashes
        assert storage.exists("test.txt")
        assert storage.exists("test2.txt")
        assert os.path.exists(os.path.join(storage_path, "test.txt"))
        assert os.path.exists(os.path.join(storage_path, "test2.txt"))
    
    def test_store_multiple_files(self, temp_dir):
        """Test storing multiple files"""
        storage_path = os.path.join(temp_dir, "storage")
        storage = FilesystemStorage(storage_path)
        storage.store("file1.txt", b"content1")
        storage.store("file2.txt", b"content2")
        storage.store("subdir/file3.txt", b"content3")
        
        # Verify all files exist
        assert storage.exists("file1.txt")
        assert storage.exists("file2.txt")
        assert storage.exists("subdir/file3.txt")
        
        # Verify content
        with open(os.path.join(storage_path, "file1.txt"), "rb") as f:
            assert f.read() == b"content1"
        with open(os.path.join(storage_path, "file2.txt"), "rb") as f:
            assert f.read() == b"content2"
        with open(os.path.join(storage_path, "subdir", "file3.txt"), "rb") as f:
            assert f.read() == b"content3"

