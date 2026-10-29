# api-detection Specification

## Purpose
Document the implemented api-detection behavior maintained by apibackuper.
## Requirements
### Requirement: Detection command
The system SHALL provide an `apibackuper detect` command that samples a project
endpoint and suggests pagination mode, data key, and total count key, and can
optionally write a starter YAML file.

#### Scenario: Detection output
- **WHEN** a user runs `apibackuper detect` for a project
- **THEN** the command prints suggested `iterate_by`, `data_key`, and
  `total_number_key` values

### Requirement: Detection flag in config
The system SHALL support a `project.detect: true` setting to run detection and
apply suggestions during a backup run.

#### Scenario: Detect flag applies suggestions
- **WHEN** `project.detect` is enabled for a run
- **THEN** detected pagination and data keys are applied for that run

### Requirement: Cursor mode detection
`apibackuper detect` SHALL suggest `iterate_by: next_url` with `data.next_url_key`
when the sampled JSON response contains a next-link field such as `next`,
`links.next` or `@odata.nextLink`, `iterate_by: cursor` with
`data.next_cursor_key` for fields such as `next_cursor` or `cursor.next`, and
`iterate_by: link_header` when the response has a `Link` header with
`rel="next"`.

#### Scenario: Next link in body
- **WHEN** the sample response is `{"results": [...], "next": "https://api.example/items?page=2"}`
- **THEN** detect suggests `iterate_by: next_url` and `next_url_key: next`

#### Scenario: Link header present
- **WHEN** the sample response has `Link: <https://api.example/items?page=2>; rel="next"`
- **THEN** detect suggests `iterate_by: link_header`

