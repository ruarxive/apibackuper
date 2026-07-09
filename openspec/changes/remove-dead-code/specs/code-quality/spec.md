## REMOVED Requirements
### Requirement: HTTPClient standalone class
**Reason**: The `HTTPClient` class in `cmds/http_client.py` is never imported
or used in the active source tree. Its logic is duplicated in
`ProjectBuilder._single_request()`. Deleting it removes 227 lines of dead code
and eliminates confusion about which class is authoritative.
**Migration**: No migration needed. The `test_http_client.py` tests reference
dead code and should be deleted alongside it.

## MODIFIED Requirements
### Requirement: Error handling for missing config files
The system SHALL report missing config files through a single code path
rather than copy-pasting the same error message block across multiple
command methods.

#### Scenario: Config file not found
- **WHEN** a user runs any command and the config file does not exist
- **THEN** a consistent error message is displayed
- **AND** the system exits with a non-zero status code

### Requirement: CLI command error handling
The system SHALL handle common exceptions (file not found, permission errors,
runtime errors) through a shared mechanism rather than per-command
copy-pasted try/except blocks.

#### Scenario: Permission error on config file
- **WHEN** a user runs a command without read permission on the config file
- **THEN** the error is caught and reported consistently across all commands
