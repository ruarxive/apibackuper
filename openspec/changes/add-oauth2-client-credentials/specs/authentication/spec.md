## ADDED Requirements
### Requirement: OAuth2 client-credentials grant
With `auth.type: oauth2` and `auth.grant_type: client_credentials`, the system
SHALL request an access token from `auth.auth_url` with
`grant_type=client_credentials`, the configured `scope` and `audience`, before
the first API request, and SHALL send it as `Authorization: Bearer <token>`.

#### Scenario: Token fetched before the first request
- **WHEN** a run starts with client credentials configured and no token
- **THEN** one token request is sent to `auth.auth_url` before the first page request
- **AND** the page request carries the returned access token

### Requirement: OAuth2 client authentication
Token and refresh requests SHALL authenticate the client with HTTP Basic
(`client_secret_basic`, the default) or with `client_id` and `client_secret`
in the request body (`client_secret_post`). Refresh-token requests SHALL
include client authentication when `auth.client_id` is set.

#### Scenario: Body client authentication
- **WHEN** `client_auth_method` is `client_secret_post`
- **THEN** the token request body contains `client_id` and `client_secret` and no `Authorization` header

### Requirement: Proactive token refresh
The system SHALL obtain a new token when the current token is within 60
seconds of the expiry given by `expires_in`, and after a 401 response. It SHALL
retry the failed request once with the new token.

#### Scenario: Token expires during a long run
- **WHEN** the token's `expires_in` elapses during collection
- **THEN** a new token is requested before the next page request
- **AND** no page request is sent with the expired token

### Requirement: Serialized token refresh
Concurrent requests SHALL share one token refresh. While a refresh is in
progress, other requests SHALL wait for its result instead of requesting
their own token.

#### Scenario: Parallel pages
- **WHEN** four parallel page requests need a token at the same time
- **THEN** exactly one token request is sent

### Requirement: OAuth2 secret handling
The client secret SHALL be read from `auth.client_secret`, an environment
placeholder or `auth.client_secret_file`. A missing or empty secret file SHALL
be a configuration error. The client secret, access tokens and refresh tokens
SHALL NOT appear in logs or error messages.

#### Scenario: Token endpoint failure
- **WHEN** the token endpoint returns HTTP 400 with the request echoed in its body
- **THEN** the run fails with a message that contains neither the client secret nor any token
