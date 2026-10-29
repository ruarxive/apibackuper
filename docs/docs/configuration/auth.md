---
title: "Authentication"
description: "Choose Basic, Bearer, API key or OAuth2 credentials and understand loading, refresh and failure behavior"
---
# Authentication

Configure `auth` when the API requires credentials. Leave the section out for
public APIs; `auth.type: none` is not a supported schema value. The same project
authentication is used by backup, update, estimation, detection, follow and
built-in file downloads.

## Choose the authentication method

| The API expects | Set `auth.type` | Required values | Sent on requests |
|-----------------|-----------------|-----------------|------------------|
| Username/password | `basic` | `username` and `password` or `password_file` | HTTP Basic Authorization |
| Existing access token | `bearer` | `token` or `token_file` | `Authorization: Bearer …` |
| Key in a named header | `apikey` | `api_key`; optionally `api_key_header` | `X-API-Key: …` by default |
| Access token with supported refresh endpoint | `oauth2` | Existing token; `auth_url` and `refresh_token` for refresh | Bearer header, refresh on 401 |

Choose the API's documented scheme. A Bearer token does not imply that the
service supports the OAuth2 refresh flow implemented here. API keys in query
parameters are not selected by `api_key_header`; that option always names a
header.

## Supply secrets from the environment

```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

Set the variable in the environment used to launch the command:

```bash
export API_TOKEN='replace-with-your-access-token'
apibackuper validate-config --strict
apibackuper run full --dry-run
```

In PowerShell, use `$env:API_TOKEN = 'replace-with-your-access-token'`.
An unset or empty `${API_TOKEN}` stops loading. `run full` reports the unresolved
variable with status 2; validation and offline plans fail with status 1.
`${VAR:-default}` supplies a default for unset/empty values, but use defaults
only for non-sensitive settings. A `.env` file is not loaded automatically.

Expansion happens when YAML is loaded, before validation. Request JSON files
do not expand `${VAR}`. Changing an environment variable after a running process
has loaded its project does not update that process's credentials.

## Read a credential file

```yaml
auth:
  type: bearer
  token_file: /run/secrets/catalog_token
```

The file should contain the credential itself, without `Bearer ` or JSON
wrapping. Leading/trailing whitespace, including a final newline, is stripped.
Relative file paths resolve from the **process working directory**, not `-p`.
Use absolute paths for jobs launched from multiple locations.

An inline `token` takes precedence over `token_file`; `password` similarly
precedes `password_file`. Remove an old inline value when switching to a file.
A missing or empty file is a configuration error: `validate-config` reports it,
and commands that send requests stop before the first request instead of
continuing without credentials. The schema alone does not verify file existence. Files are read at project load, not on every
request. Use a new command invocation to load a replacement file.

## Basic authentication

```yaml
auth:
  type: basic
  username: archive_reader
  password_file: /run/secrets/catalog_password
```

For environment-based credentials, replace `password_file` with
`password: "${API_PASSWORD}"`. Both username and a non-empty password are needed
to construct the header. Use the API's HTTPS endpoint: HTTP Basic encoding is
not encryption.

## Bearer tokens

```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

Supply only the token value. Including the word `Bearer` in the value would
produce a second prefix in the outgoing header. Static Bearer mode has no
refresh behavior; an expired token must be replaced outside apibackuper.
Template: `examples/templates/bearer-auth.yaml`.

## API keys

```yaml
auth:
  type: apikey
  api_key: "${CATALOG_API_KEY}"
  api_key_header: X-API-Key
```

Change `api_key_header` only if the service requires a different header name,
for example `X-Catalog-Key`. There is no `api_key_file` setting; use an environment
variable for this method. For another custom authentication header, a trusted
hook can supply it, subject to the project's normal auth-header precedence.

## OAuth2 refresh

Obtain an access token outside apibackuper, then configure:

```yaml
auth:
  type: oauth2
  token: "${ACCESS_TOKEN}"
  auth_url: https://api.example.com/oauth/token
  refresh_token: "${REFRESH_TOKEN}"
```

`token_file` can replace the inline access token. The refresh token is supplied
through `refresh_token`, including environment expansion; there is no separate
refresh-token-file option.

The refresh sequence is:

1. Send the API request with the current Bearer token.
2. If it returns HTTP 401, POST form fields `grant_type=refresh_token` and
   `refresh_token` to `auth_url`.
3. Require HTTP 200 with JSON containing `access_token`, for example:

```json
{"access_token": "replacement-access-token", "refresh_token": "replacement-refresh-token"}
```

4. Keep the new access token and optional rotated refresh token in memory, then
   retry the original API request with its original body/query and new header.

Refresh uses configured connection/read timeouts and SSL verification. It is
triggered by a 401, not proactively by expiry time; a 403 does not trigger it.
Refresh failures are logged and the unsuccessful request is handled by the
normal [HTTP error policy](/configuration/rate-limiting-and-requests).

### Restart and provider limitations

Refreshed tokens are **not persisted** to YAML, the environment or `token_file`.
If the provider invalidates an old refresh token on rotation, arrange to provision
current credentials before restarting or resuming. Reusing the original file
cannot recover a rotated refresh token automatically.

Browser authorization, authorization-code/PKCE and client-credentials grants
are not implemented. Refresh does not add dedicated `client_id`, `client_secret`
or scope fields. Providers requiring those fields need external token management.

## Header precedence and scope

`headers.json` can add ordinary headers such as `Accept` or a client identifier.
The auth handler overrides a conflicting authentication header when constructing
the request. Use one source for a given credential instead of maintaining both
`Authorization` in JSON and `auth` in YAML.

Follow and attachment requests also receive the project's authentication.
Use URLs that are allowed to receive those credentials, especially when records
contain absolute URLs on another host. When a response redirects to another
host, `Authorization`, the configured API-key header and other headers with
credential-like names (`Cookie`, `X-Auth-Token`, `api_key`, …) are dropped from
the redirected request. The optional aria2 downloader is a
separate service and does not inherit the built-in authentication policy.

## Check authentication problems

| Symptom | What to verify |
|---------|----------------|
| Unresolved variable error | Variable is exported in the shell/service launching the command; `.env` is not automatic |
| No usable token from a file | Absolute path, readability, non-empty content and absence of an overriding inline value |
| HTTP 401 | Token value/prefix, expiry, endpoint, account and supported refresh configuration |
| HTTP 403 | Token permissions and API access policy; OAuth refresh is only triggered by 401 |
| Restart breaks OAuth refresh | Provider rotates refresh tokens; the previous process did not persist the new value |
| Dry-run succeeds but API rejects credentials | Dry-run checks local configuration and reports auth type; it makes no authentication request |

Use `--verbose` on commands that support it and inspect the log. Recognized
credential fields are redacted in shared diagnostics, but custom hook output
and API-specific free text still need care before sharing. See
[protected APIs](/use-cases/protected-apis) for a complete operational example.
