## ADDED Requirements
### Requirement: Incremental update mode
The system SHALL support an update mode that uses a persistent per-project state
file to fetch only new or changed records.

#### Scenario: Update mode uses stored state
- **WHEN** `apibackuper update` runs for a project with saved state
- **THEN** only records after the stored state are requested and the state is
  updated after completion

### Requirement: Update mode configuration
The system SHALL accept `update_mode` values `by_change_key`, `by_timestamp`, or
`custom_script`, and a `change_key` configuration to support change detection.

#### Scenario: Change-key update
- **WHEN** `update_mode` is `by_change_key` and `change_key` is configured
- **THEN** requests filter or compare records using the configured change key
