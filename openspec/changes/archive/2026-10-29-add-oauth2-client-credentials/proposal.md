# Change: Add OAuth2 client-credentials grant and client authentication

## Why
`auth.type: oauth2` accepts only a pre-issued access token and a refresh
token (`apibackuper/auth.py`). It cannot obtain a token itself, it sends no
`client_id`/`client_secret` when refreshing (most providers require client
authentication, RFC 6749 §6), and it refreshes only after a 401. Unattended
backups of machine-to-machine APIs therefore need an external token script.
dlt, Airbyte and the Singer SDK all support the client-credentials grant.
`docs/docs/configuration/auth.md` currently lists it as not implemented.

## What Changes
- New `auth.grant_type`: `refresh_token` (default, current behaviour) or
  `client_credentials`.
- New fields: `auth.client_id`, `auth.client_secret`,
  `auth.client_secret_file`, `auth.scope`, `auth.audience`, and
  `auth.client_auth_method` (`client_secret_basic`, the default, or
  `client_secret_post`). `auth.auth_url` remains the token endpoint.
- With `client_credentials`, the token is fetched before the first request and
  again before it expires (`expires_in` minus 60 seconds), or after a 401.
- Refresh-token requests include client authentication when `client_id` is set.
- Token refresh is serialized with a lock so parallel page fetches do not
  request several tokens at once.
- Secrets follow the existing rules: `${VAR}` placeholders, a missing or empty
  `client_secret_file` is a configuration error, and diagnostics redact the
  secret and tokens.
- `validate-config` checks the fields required by the selected grant.

## Impact
- Affected specs: new `authentication` capability
- Affected code: `apibackuper/auth.py`, `apibackuper/cmds/project.py`
  (`_single_request`, validation), `apibackuper/schemas/config_schema.json`,
  `docs/docs/configuration/auth.md`
- Not breaking: configurations without `grant_type` keep the refresh-token
  behaviour.
