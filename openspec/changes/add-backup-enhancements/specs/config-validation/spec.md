## ADDED Requirements
### Requirement: YAML-first configuration
The system SHALL treat YAML as the primary configuration format and SHALL emit
a deprecation warning when INI configuration is used.

#### Scenario: INI usage warning
- **WHEN** a project is loaded from an INI file
- **THEN** the run proceeds and a deprecation warning is displayed

### Requirement: Strict validation and errors
The system SHALL validate configuration on run start and provide a
`apibackuper validate-config` command that reports strict, verbose errors
including the failing configuration path.

#### Scenario: Missing required key
- **WHEN** a required key is missing in the configuration
- **THEN** the error output includes the full path to the missing key
