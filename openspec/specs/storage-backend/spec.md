# storage-backend Specification

## Purpose
Document the implemented storage-backend behavior maintained by apibackuper.
## Requirements
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

### Requirement: Reserved capture member names
Storage backends SHALL treat only members whose basename starts with `page_`
as pages. Members named `exchange_N.json` and `raw_N.<ext>` SHALL be stored and
listed as objects, and SHALL NOT be counted, exported as records or used to
compute resume positions.

#### Scenario: Capture members ignored by page listing
- **WHEN** an archive contains `page_1.json`, `exchange_1.json` and `raw_1.xml`
- **THEN** listing pages returns only `page_1.json`

### Requirement: Per-generation ZIP archives
With ZIP storage, the backend SHALL store members named `runs/<id>/...` in the
archive `storage.zip.runs/<id>.zip` beside `storage.zip`, and SHALL list and read members of
the base archive, of legacy generations inside it and of every generation
archive as one set of names.

#### Scenario: Update leaves the base archive untouched
- **WHEN** an update saves `runs/<id>/page_1.json`
- **THEN** the member is written to `storage.zip.runs/<id>.zip`
- **AND** `storage.zip` is not rewritten

#### Scenario: Mixed legacy layout
- **WHEN** `storage.zip` contains `runs/old/page_1.json` and `runs/new.zip` exists
- **THEN** listing pages returns the base pages, `runs/old/page_1.json` and the pages of `runs/new.zip`

