## ADDED Requirements
### Requirement: Declarative response rules
The system SHALL evaluate `request.response_rules` in order for every response
of a page, follow or file request, and SHALL apply the action of the first rule
whose `status`, `body_key`/`body_value` and `content_type` conditions all match.

#### Scenario: Error body with status 200
- **WHEN** a rule `{body_key: error, action: retry}` exists and a page returns `200` with `{"error": "busy"}`
- **THEN** the request is retried under the retry policy
- **AND** the page is not saved until a response without `error` arrives

#### Scenario: Accepted status
- **WHEN** a rule `{status: 404, action: accept}` exists and a page returns 404 with an empty list
- **THEN** the page is processed as a successful response

### Requirement: Missing objects by rule
The `missing` action SHALL record a follow key or file as gone and continue
with the next one, and SHALL fail the run when it applies to a page request.

#### Scenario: Gone detail object
- **WHEN** a follow request matches a rule with action `missing`
- **THEN** the key is listed in `details.missing.json` and the follow run continues

### Requirement: Rate-limit header waits
Before retrying, the system SHALL wait for the first header in
`request.retry.wait_headers` that is present, interpreting its value as
seconds, an HTTP date or a Unix timestamp. A wait longer than
`request.retry.max_wait` SHALL fail the run instead of sleeping.

#### Scenario: Reset timestamp
- **WHEN** a 429 response carries `X-RateLimit-Reset` set 30 seconds in the future and that header is configured
- **THEN** the retry is sent after about 30 seconds

#### Scenario: Wait exceeds the cap
- **WHEN** the header asks for one hour and `max_wait` is 300 seconds
- **THEN** the run fails as incomplete without waiting
