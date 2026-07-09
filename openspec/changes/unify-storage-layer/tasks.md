## 1. New Backend Implementation
- [ ] 1.1 Create `FilesystemBackend` in `storage/backends.py` implementing `StorageBackend`
- [ ] 1.2 Implement `save_page()`, `save_object()`, `list_objects()`, `get_object()`
- [ ] 1.3 Use context managers for all file I/O (no manual close)
- [ ] 1.4 Add path sanitization to prevent directory traversal

## 2. Migration
- [ ] 2.1 Update `build_storage_backend()` to support `filesystem` type
- [ ] 2.2 Replace `FilesystemStorage` usage in `project.py:getfiles()` with `FilesystemBackend`
- [ ] 2.3 Remove import of legacy classes from `project.py`

## 3. Deprecation
- [ ] 3.1 Add deprecation warnings to `FileStorage`, `ZipFileStorage`, `FilesystemStorage`
- [ ] 3.2 Update tests to use new backend classes
- [ ] 3.3 Document migration path in README

## 4. Security Fix
- [ ] 4.1 Fix SQL injection pattern in `SqliteStorageBackend` (use allowlist for table names)
- [ ] 4.2 Add test for SQL injection attempt via table name

## 5. Verification
- [ ] 5.1 Confirm all storage tests pass
- [ ] 5.2 Confirm `getfiles()` works with `FilesystemBackend`
- [ ] 5.3 Confirm no remaining references to legacy classes in active code
