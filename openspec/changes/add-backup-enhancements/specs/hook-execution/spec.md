## ADDED Requirements
### Requirement: Hook configuration
The system SHALL load optional hook scripts from configuration for
`before_run`, `before_request`, `after_response`, `after_page`, and `after_run`.

#### Scenario: Hook script configured
- **WHEN** a hook path is configured for `before_request`
- **THEN** the hook is invoked before each request is sent

### Requirement: Hook effects on requests
The system SHALL allow `before_request` hooks to modify request URL, parameters,
or headers before dispatch.

#### Scenario: Hook modifies headers
- **WHEN** a `before_request` hook sets a header value
- **THEN** the outgoing request includes the modified header
