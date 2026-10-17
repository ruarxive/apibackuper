## ADDED Requirements
### Requirement: Typed and validated configuration
The loader SHALL preserve typed YAML lists through normalization and reject
invalid execution settings before modifying backup storage.

#### Scenario: Retry code list
- **WHEN** retry_on_errors is a YAML integer list
- **THEN** the configured codes are used without string-list parsing errors

### Requirement: Optional record path
Record extraction SHALL support root arrays and normalized XML data without data_key.

#### Scenario: Root JSON array
- **WHEN** a paginated endpoint returns a root array with no data_key
- **THEN** all records are counted, stored and exported without exceptions
