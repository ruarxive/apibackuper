# Change: Unify dual storage abstractions into single backend system

## Why
Two parallel storage systems exist: legacy `FileStorage`/`ZipFileStorage`/
`FilesystemStorage` in `storage/__init__.py` and the new `StorageBackend`
ABC with `ZipStorageBackend`/`SqliteStorageBackend` in `storage/backends.py`.
Both wrap `ZipFile` with incompatible interfaces, forcing developers to
maintain two code paths for the same operation. The old classes are imported
into `project.py` but only `FilesystemStorage` is used actively.

## What Changes
- Port `FilesystemStorage` to a `FilesystemBackend` implementing `StorageBackend`
- Mark legacy `FileStorage`/`ZipFileStorage` as deprecated
- Migrate all active code to use only `StorageBackend` implementations
- Remove the old legacy classes in a follow-up release
- Fix SQL injection pattern in `SqliteStorageBackend` (parameterized queries)
- Fix table name interpolation in SELECT statements

## Impact
- Affected specs: storage-backend
- Affected code: `apibackuper/storage/__init__.py`, `apibackuper/storage/backends.py`,
  `apibackuper/cmds/project.py`
