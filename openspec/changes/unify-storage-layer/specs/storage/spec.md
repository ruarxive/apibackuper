## ADDED Requirements
### Requirement: FilesystemBackend implementation
The system SHALL provide a `FilesystemBackend` implementing `StorageBackend`
that stores pages and objects as files on the local filesystem.

#### Scenario: Store page to filesystem
- **WHEN** a page is saved via `FilesystemBackend.save_page()`
- **THEN** the page content is written to a file under the base path
- **AND** `list_objects()` returns the stored page names

### Requirement: Single storage abstraction
The system SHALL use only the `StorageBackend` ABC for all active storage
operations. Legacy `FileStorage`/`ZipFileStorage` classes SHALL be deprecated.

#### Scenario: No direct legacy class usage
- **WHEN** storage operations are performed in `project.py`
- **THEN** they use only `StorageBackend` implementations
- **AND** no `FileStorage` or `ZipFileStorage` instances are created

## MODIFIED Requirements
### Requirement: SqliteStorageBackend query safety
The system SHALL use parameterized queries for all database operations
including table-safe Dynamic SQL.

#### Scenario: List objects query
- **WHEN** `SqliteStorageBackend.list_objects()` is called
- **THEN** the table name is validated against an allowlist
- **AND** the query cannot be injected via table name

## REMOVED Requirements
### Requirement: Legacy FileStorage class
**Reason**: Superseded by `StorageBackend` ABC. All active functionality is
covered by `ZipStorageBackend` and `FilesystemBackend`.
**Migration**: Users of legacy classes should migrate to `build_storage_backend()`.
