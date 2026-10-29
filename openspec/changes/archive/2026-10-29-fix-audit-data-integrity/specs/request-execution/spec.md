## ADDED Requirements
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
