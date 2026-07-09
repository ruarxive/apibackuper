## ADDED Requirements
### Requirement: Configurable SSL verification
The system SHALL honor a `request.verify_ssl` configuration option that
controls whether SSL certificates are validated. The default value SHALL be
`true`.

#### Scenario: SSL verification enabled by default
- **WHEN** a user runs `follow` or `estimate` without configuring `verify_ssl`
- **THEN** SSL certificates are validated
- **AND** self-signed or expired certificates cause the request to fail

#### Scenario: SSL verification explicitly disabled
- **WHEN** a user sets `request.verify_ssl: false` in config
- **THEN** SSL certificate validation is skipped for follow and estimate requests
- **AND** a warning is logged about the security implication

### Requirement: Path traversal prevention
The system SHALL reject or sanitize file paths that attempt directory
traversal outside the storage base path.

#### Scenario: Path traversal attempt
- **WHEN** a filename containing `../../etc/passwd` is passed to storage
- **THEN** the system raises a `ValueError` or sanitizes to `etc/passwd`
- **AND** no file is written outside the storage directory

### Requirement: Safe SQL query construction
The system SHALL prevent SQL injection via dynamic table names in the
SQLite storage backend.

#### Scenario: Internal table name resolution
- **WHEN** `SqliteStorageBackend` builds a SELECT query
- **THEN** the table name is validated against `{"pages", "objects"}`
- **AND** any other value raises a `ValueError`

## MODIFIED Requirements
### Requirement: Credential storage
The system SHALL support loading sensitive credentials (passwords, tokens,
API keys) from environment variables rather than storing them in plaintext
config files.

#### Scenario: Environment variable reference in config
- **WHEN** a user sets `password: "${API_PASSWORD}"` in config
- **THEN** the system reads the value from the `API_PASSWORD` environment variable
- **AND** if the variable is unset, a clear error is reported
