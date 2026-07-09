## ADDED Requirements
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
