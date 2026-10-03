## 1. New Backend Implementation
- [x] 1.1 Create `FilesystemBackend` in `storage/backends.py` implementing `StorageBackend`
- [x] 1.2 Implement `save_page()`, `save_object()`, `list_objects()`, `get_object()`
- [x] 1.3 Use context managers for all file I/O (no manual close)
- [x] 1.4 Add path sanitization to prevent directory traversal

## 2. Migration
- [x] 2.1 Update `build_storage_backend()` to support `filesystem` type
- [x] 2.2 Replace `FilesystemStorage` usage in `project.py:getfiles()` with `FilesystemBackend`
- [x] 2.3 Remove import of legacy classes from `project.py`

## 3. Deprecation
- [x] 3.1 Add deprecation warnings to `FileStorage`, `ZipFileStorage`, `FilesystemStorage`
- [ ] 3.2 Update tests to use new backend classes — legacy test classes still exist alongside new ones
- [ ] 3.3 Document migration path in README — pending

## 4. Security Fix
- [x] 4.1 Fix SQL injection pattern in `SqliteStorageBackend` (use allowlist for table names)
- [x] 4.2 Add test for SQL injection attempt via table name

## 5. Verification
- [x] 5.1 Confirm all storage tests pass
- [x] 5.2 Confirm `getfiles()` works with `FilesystemBackend`
- [x] 5.3 Confirm no remaining references to legacy classes in active code (only in `storage/__init__.py` for backward compat and in `tests/`)