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

### Requirement: Pagination probing
Unless the configuration already sets the parameter its pagination mode needs,
`apibackuper detect` SHALL send additional requests to find the pagination
parameters: a page parameter when page 2 returns other records than the first
response and page 1 returns the same ones, otherwise an offset parameter when
an offset equal to the first page's size returns other records, then a size
parameter when the API returns exactly the requested number of records. It
SHALL suggest `iterate_by`, the parameter names and a `page_size_limit` equal
to the size the API honours, and SHALL report the record fields, one sample
record and warnings for anything it could not find.

#### Scenario: Page-number API
- **WHEN** detect probes an API that pages with `page` and `per_page` and caps pages at 50 records
- **THEN** it suggests `iterate_by: page`, `page_number_param: page`,
  `page_size_param: per_page` and `page_size_limit: 50`

#### Scenario: No parameter changes the records
- **WHEN** no candidate page or offset parameter changes the returned records
- **THEN** detect suggests no pagination parameter and reports a warning to set it by hand

### Requirement: Project initialization from a probed endpoint
The system SHALL provide `apibackuper init NAME --url URL` that sends one
request using the given method, headers, authentication and body, detects the
records path, count fields and pagination mode, and writes a complete
`apibackuper.yaml` (plus `headers.json` and `params.json` when needed) into a
new project directory. GET query parameters SHALL move from the URL into
`params.json`, except detected pagination parameters. The command SHALL print a
JSON report with the detected settings, the list of record fields, one sample
record, warnings for anything it could not detect, validation results and the
next commands to run. Credentials SHALL be written as `${VAR}` placeholders, not
as literal values, and the endpoint SHALL NOT be probed while the variable is
unset. An existing configuration SHALL NOT be replaced without `--force`.

#### Scenario: Initialize a POST search API
- **WHEN** a user runs `apibackuper init search --url https://api.example/search --method POST --body '{"q": "*"}'`
- **THEN** `search/apibackuper.yaml` and `search/params.json` are written and
  the report lists the detected `data_key` and pagination settings

#### Scenario: Authenticated API without the secret
- **WHEN** a user runs `apibackuper init private --url URL --auth bearer` and `API_TOKEN` is unset
- **THEN** the configuration contains `token: ${API_TOKEN}`, no request is sent,
  and the report warns that the endpoint was not probed

#### Scenario: Pagination cannot be detected
- **WHEN** the probed response has records but no recognizable pagination fields
- **THEN** the report contains a warning naming the `params` fields to set and
  the written configuration still validates

