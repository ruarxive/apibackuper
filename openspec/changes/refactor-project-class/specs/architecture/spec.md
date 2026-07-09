## ADDED Requirements
### Requirement: Modular component architecture
The system SHALL organize business logic into focused components with clear
interfaces rather than a single monolithic class.

#### Scenario: Independent component testing
- **WHEN** a developer needs to test HTTP retry behavior
- **THEN** they can test `RequestEngine` without loading config or accessing storage

#### Scenario: Adding a new export format
- **WHEN** a developer needs to add CSV export
- **THEN** they modify only `ExportPipeline` without touching HTTP or config logic

### Requirement: ConfigProcessor component
The system SHALL provide a dedicated component for loading, validating, and
normalizing project configuration.

#### Scenario: YAML config loading
- **WHEN** a YAML config file is provided
- **THEN** `ConfigProcessor` loads and validates it against the schema
- **AND** returns normalized defaults for missing optional keys

### Requirement: RequestEngine component
The system SHALL provide a dedicated component for HTTP request execution with
integrated auth, rate limiting, and retry logic.

#### Scenario: Authenticated request
- **WHEN** OAuth2 credentials are configured
- **THEN** `RequestEngine` attaches the bearer token to each request
- **AND** refreshes the token on 401 responses

### Requirement: ExportPipeline component
The system SHALL provide a dedicated component for exporting archived data
in multiple formats.

#### Scenario: JSONL export
- **WHEN** the user requests JSONL output
- **THEN** `ExportPipeline` reads pages from storage and writes one JSON object per line

### Requirement: HookRunner component
The system SHALL provide a dedicated component for loading and executing
user-provided hook scripts at defined lifecycle points.

#### Scenario: Before-run hook
- **WHEN** a project defines a `before_run` hook
- **THEN** `HookRunner` loads and executes it before the first API request
