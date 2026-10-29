---
title: "Protected APIs"
description: "Run a credentialed backup with explicit quotas, bounded retries, token recovery and verifiable results"
---
# Protected APIs

A protected collection needs valid credentials, permission to read the complete
dataset and a request policy that fits the service's quota. This walkthrough
combines those requirements in one project, then covers expiring tokens and
interrupted runs.

The example endpoint is illustrative. It assumes a Bearer-protected, read-only
GET API that accepts one-based `page`/`per_page` and returns
`{"total":N,"items":[...]}`. Replace its URL, fields and quotas with your
provider's contract. The local quick-start server does not test authentication.

## 1. Obtain access and choose the credential source

Obtain a token through your provider's normal authorization process and confirm
the account can read the intended collection. API access can still be limited
by organization, tenant, role or field-level permissions even with HTTP 200.
Record the expected scope/count so the resulting backup can be checked.

For an interactive run, provide the token in the launching environment:

```bash
export API_TOKEN='replace-with-your-access-token'
```

In PowerShell, use `$env:API_TOKEN = 'replace-with-your-access-token'`. Supply
the token value without the `Bearer ` prefix. YAML expands `${API_TOKEN}` at
project load; a `.env` file is not loaded automatically and JSON request files
do not expand variables. Prefer your deployment's secret provisioning mechanism
for unattended jobs rather than storing credentials in repository files.

## 2. Save a complete starting configuration

Create a dedicated project and save `apibackuper.yaml`:

```yaml config
settings:
  name: protected-catalog
  checkpoint_interval_pages: 5
project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page
  default_delay: 0
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
data:
  data_key: items
  total_number_key: total
  item_key: id
storage:
  storage_type: zip
auth:
  type: bearer
  token: "${API_TOKEN}"
rate_limit:
  enabled: true
  requests_per_second: 2
  requests_per_minute: 100
  burst_size: 1
request:
  parallelism: 1
  connect_timeout: 10
  read_timeout: 60
  verify_ssl: true
  retry:
    max_retries: 3
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 10
    retry_on_status: [429, 500, 502, 503, 504]
error_handling:
  continue_on_error: false
  max_consecutive_errors: 3
```

These are conservative example limits, not a statement of the provider's quota.
Add ordinary non-secret headers in `headers.json` if required:

```json
{"Accept": "application/json", "X-Client-Name": "catalog-archive"}
```

The auth handler supplies `Authorization`. Avoid keeping a competing copy of
that credential in JSON. Fixed scope filters and stable sorting belong in
`params.json`, using only the provider's documented parameter names.

For a provisioned token file, replace the `auth` section with:

```yaml
auth:
  type: bearer
  token_file: /run/secrets/catalog_token
```

Use a readable, non-empty file containing just the token. Absolute paths avoid
working-directory ambiguity for scheduled jobs. Remove an old inline `token`
when switching to a file: inline values take precedence. Credential files are
read when the project loads, not before every HTTP request.

## 3. Separate local checks from an access test

From the project directory:

```bash
apibackuper validate-config --strict
apibackuper run full --dry-run
```

These checks are offline. They can detect an unresolved environment variable or
invalid option, but do not establish that a token file exists, a credential is
accepted, or the account can see all records.

Then sample the real service:

```bash
apibackuper estimate full
```

This makes a live API request. Check the count and response shape against your
expected authorization scope before running the full collection. An empty
collection or a smaller total can be a permissions/filter problem rather than
a pagination problem. Authentication success is not proof of completeness.

## 4. Collect, verify and recover

```bash
apibackuper run full --verbose
apibackuper info --json
apibackuper export protected-items.jsonl
```

Check the backup command's exit status and inspect exported counts, distinct IDs
and representative fields. Keep exports under the same access policy as the
source data; they contain the returned records without an API access check.

If a token expires and the run stops, obtain a replacement and update the
credential source. Start a new CLI invocation so it loads the replacement:

```bash
apibackuper run full --resume
```

Keep the same account scope, endpoint, filters and pagination while resuming.
Preserve the checkpoint, `.partial` archive and matching `.journal` sidecar.
For an interrupted update use `apibackuper update --resume` instead. A failed
full backup keeps the previous published archive, and failed updates do not
advance successful watermarks. `info` may therefore describe earlier success;
use the latest command result and logs to assess the failure.

## 5. Tune the HTTP budget from observed behavior

| Setting in the example | Operational effect |
|------------------------|--------------------|
| `parallelism: 1` | One backup-page worker; raise only after testing quota and stable pagination |
| `requests_per_second: 2`, `burst_size: 1` | Small per-process token bucket without a large initial burst |
| `requests_per_minute: 100` | Additional rolling minute cap; both limits apply |
| `connect_timeout: 10` | Bound connection establishment |
| `read_timeout: 60` | Bound waits for response data, not total backup duration |
| `max_retries: 3` | Up to four ordinary attempts per failed request |
| Exponential delay from 1 second | Retry waits of 1, 2 and 4 seconds, unless Retry-After overrides them |
| `continue_on_error: false` | Stop collection when a page remains unresolved after retries |

Retryable attempts share this process's limiter. Other CLI processes or
applications using the account do not share it. Redirects and OAuth refresh/
immediate replay can add HTTP exchanges within an attempt, so reserve headroom
if the provider counts every exchange. Follow/file transfers also consume quota;
aria2 uses a separate policy.

A `Retry-After` value, in seconds or as an HTTP date, can exceed `max_delay`.
Increasing retries does not repair a 401/403. Set the active connection/read
fields rather than relying on the legacy `request.timeout` setting. For POST
search APIs, confirm request replay is acceptable before using retries.
See [request policy](/configuration/rate-limiting-and-requests).

## Other authentication schemes and token rotation

Choose the provider's actual scheme rather than adding headers experimentally:

| Provider contract | Configuration | Restart consideration |
|-------------------|---------------|-----------------------|
| HTTP Basic | `type: basic`, `username`, `password` or `password_file` | Load current password in each process |
| API key in a header | `type: apikey`, `api_key`, optionally `api_key_header` | Default header is `X-API-Key`; no `api_key_file` option |
| Existing Bearer token | `type: bearer`, `token` or `token_file` | Replace expired token externally |
| Compatible OAuth refresh endpoint | `type: oauth2`, token, `auth_url`, `refresh_token` | Refreshed/rotated values remain in memory only |

A compatible OAuth configuration is:

```yaml
auth:
  type: oauth2
  token: "${ACCESS_TOKEN}"
  refresh_token: "${REFRESH_TOKEN}"
  auth_url: https://api.example.com/oauth/token
```

Both variables must be provided to the command. On HTTP 401 the client submits
`grant_type=refresh_token` and the refresh token as form data, expects HTTP 200
with `access_token`, then replays the original request. HTTP 403 does not
trigger refresh. There is no browser login, authorization-code/PKCE or built-in
client-credentials grant, and no dedicated client ID/secret refresh fields.

Updated tokens are not written back to YAML, files or the environment. If the
provider rotates refresh tokens, provision a current token for the next process;
resuming with an invalidated original refresh token cannot recover it. Providers
with another refresh contract need external token management. See
[authentication](/configuration/auth#oauth2-refresh).

## TLS, linked hosts and unattended runs

Keep `verify_ssl: true`. A TLS failure can indicate the wrong endpoint, trust
configuration or an intercepting proxy; disabling verification does not fix
authentication. The option is boolean, not a CA-bundle path. See
[troubleshooting](/getting-started/troubleshooting) and the
[proxy configuration](/configuration/rate-limiting-and-requests#proxies).

Follow/detail and built-in attachment requests use project authentication too.
Verify that linked hosts are authorized recipients of those credentials before
using the [follow/files pipeline](/use-cases/follow-and-files).

For scheduled collection, use an explicit project path or working directory,
provision secrets for the scheduler's environment, prevent overlapping writers,
and check exit status before launching another run. Retain recovery files on
failure. Shared diagnostics redact recognized credentials, but review custom
headers, URL parameters, hook output and service messages before sharing logs.

| Failure | Action |
|---------|--------|
| Unresolved `${API_TOKEN}` | Export it in the environment that actually launches the CLI |
| Token file ignored | Check absolute path, content and an overriding inline token |
| HTTP 401 | Check token prefix, expiry and refresh contract; replace/provision credentials |
| HTTP 403 or unexpectedly small dataset | Check permissions, tenant/scope and filters |
| Repeated HTTP 429 | Reduce rate/burst/concurrency and account for other quota consumers |
| Timeout despite a higher `timeout` | Configure `connect_timeout` and `read_timeout` explicitly |
| OAuth works until restart | Rotated credentials were not persisted; supply current values |
