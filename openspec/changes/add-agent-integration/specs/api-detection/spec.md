## ADDED Requirements

### Requirement: Project initialization from a probed endpoint
The system SHALL provide `apibackuper init NAME --url URL` that sends one
request using the given method, headers, authentication and body, detects the
records path, count fields and pagination mode, and writes a complete
`apibackuper.yaml` (plus `headers.json` and `params.json` when given) into a new
project directory. The command SHALL print a JSON report with the detected
settings, the list of record fields, one sample record, warnings for anything
it could not detect, and the next commands to run. Credentials SHALL be written
as `${VAR}` placeholders, not as literal values.

#### Scenario: Initialize a POST search API
- **WHEN** a user runs `apibackuper init search --url https://api.example/search --method POST --body '{"q": "*"}'`
- **THEN** `search/apibackuper.yaml` and `search/params.json` are written and
  the report lists the detected `data_key` and pagination settings

#### Scenario: Pagination cannot be detected
- **WHEN** the probed response has records but no recognizable pagination fields
- **THEN** the report contains a warning naming the `params` fields to set and
  the written configuration still validates
