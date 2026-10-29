# request-execution Specification

## Purpose
Document the implemented request-execution behavior maintained by apibackuper.
## Requirements
### Requirement: Concurrency within rate limits
The system SHALL support a `request.parallelism` setting to fetch pages
concurrently while honoring configured rate limits.

#### Scenario: Parallel requests with limits
- **WHEN** `request.parallelism` is greater than one
- **THEN** multiple requests execute concurrently without exceeding limits

### Requirement: Configurable retry policy
The system SHALL support configurable retry policy settings including
max retries, backoff strategy, retry delays, and retryable status codes.

#### Scenario: Retry on transient errors
- **WHEN** a response status is configured as retryable
- **THEN** the request is retried according to the policy and `Retry-After`
  header if present

### Requirement: Shared bounded request execution
Backup, follow and file requests SHALL share authentication, TLS, timeouts,
rate limiting and bounded retries. HTTP success SHALL be independent of retryability.

#### Scenario: Permanent forbidden response
- **WHEN** an endpoint returns HTTP 403
- **THEN** it is reported as a failure and is not saved as successful data

#### Scenario: Transport retry
- **WHEN** a request times out before a response and retry budget remains
- **THEN** the request is retried with the configured controls

### Requirement: Correct query construction
Flat parameters SHALL be encoded as query parameters without losing existing query values.

#### Scenario: Existing query
- **WHEN** flat parameters are added to a URL containing a query
- **THEN** both the original and new parameters reach the endpoint correctly

### Requirement: Credential-safe diagnostics
Diagnostics SHALL redact credentials in URLs, nested values, headers and exceptions.

#### Scenario: Nested and URL tokens
- **WHEN** a failing request includes a token in its URL and nested body
- **THEN** neither token value appears in logs or CLI errors

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

