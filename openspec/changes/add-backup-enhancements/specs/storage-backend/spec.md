## ADDED Requirements
### Requirement: Storage backend abstraction
The system SHALL use a storage backend interface that provides `save_page`,
`save_object`, `list_objects`, and `get_object`.

#### Scenario: ZIP backend compatibility
- **WHEN** the ZIP backend is selected
- **THEN** existing storage behavior is preserved through the interface

### Requirement: SQLite backend
The system SHALL provide a SQLite storage backend with tables for pages and
objects and a configurable database path.

#### Scenario: SQLite storage configured
- **WHEN** `storage.storage_type` is `sqlite` and a path is provided
- **THEN** pages and objects are stored in the SQLite database
