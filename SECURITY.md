# Security Considerations

This document describes the security model of apibackuper and the risks you
should be aware of when running it.

## ⚠️ Config = executable code

apibackuper config files can reference arbitrary Python files via the
`code.postfetch`, `code.follow` and `hooks` settings.
These files are loaded and executed via ``runpy.run_path`` at the relevant
point in the run lifecycle. Examples:

```yaml
code:
  postfetch: scripts/listtodata.py
  follow: scripts/pagetodata.py
```

**Implications:**

- Anyone who can write to the project directory can get arbitrary code
  execution as the apibackuper process.
- Do not run apibackuper against untrusted project directories.
- Treat the project directory the same way you treat a checked-out shell
  script: read every line before you let it run.

Only use these features with trusted project files and scripts.

## Hook context format

Scripts configured under `hooks` run in a separate Python process, which reads
the context from a temporary JSON file and calls `hook(context)` or
`run(context)`. They have the user's filesystem and network permissions;
Python's `-I` option does not sandbox them. The context shape varies by hook.
`code.postfetch` and `code.follow` extraction scripts run inside the main
process and expose `process(content)` instead.

### `before_run`

```json
{
  "mode": "full",
  "headers": {},
  "params": {},
  "project_path": "/abs/path/to/project"
}
```

`mode` is `full`, `continue` or `update`. `before_request` adds `url` and
`page` to request headers and parameters. `after_response` also includes a
serialized response. These contexts can contain live credentials; trusted
hooks are responsible for handling them safely.

### `after_page` / `after_run`

```json
{
  "page": 5,
  "mode": "full",
  "records_processed": 1500,
  "bytes_written": 250000
}
```

```json
{
  "mode": "full",
  "pages_processed": 12,
  "records_processed": 5400,
  "bytes_processed": 1200000,
  "errors": {}
}
```

## Credentials in logs

The CLI writes `apibackuper.log` in the current working directory.
Shared HTTP diagnostics redact recognized credential keys in headers, nested
parameters, URL user information and query strings, OAuth2 errors and request
exception messages. Redaction uses `***REDACTED***` and leaves actual request
credentials unchanged. Custom hooks and API-specific free text are outside
that guarantee; review them before sharing logs.

## SSL/TLS verification

`request.verify_ssl` is a boolean and defaults to `true`. Backup, follow,
estimate, detection and file requests share this setting. Disabling it logs a
warning. The configuration loader does not accept a CA-bundle path in this field:

```yaml
request:
  verify_ssl: true
```

## OAuth2 refresh

When using OAuth2 (``auth.type = oauth2``), the refresh token POST
honours the ``verify_ssl`` setting and a 30-second timeout by default.
Failures are logged at WARNING. Rotated refresh tokens are captured.

CLI API requests pass their configured connection/read timeouts to refresh;
the 30-second default applies to standalone AuthHandler calls without a timeout.
Refreshed tokens are held in memory only and are not persisted to configuration
or credential files. See the documentation authentication page for supported
grants and restart implications.

## Path traversal in storage

Member names written to the zip and filesystem storage backends are
sanitized via ``apibackuper.storage.safe_member_name``. A name like
``../../etc/passwd`` becomes ``_/_/etc/passwd`` and cannot escape the
archive. Server-controlled filenames (from APIs and Content-Disposition
headers) are still validated; do not disable the storage layer in
untrusted environments.

## SQL injection

``SqliteStorageBackend`` uses an allowlist of table names
(``{pages, objects}``). User-supplied ``kind`` values cannot reach
``sqlite3`` as table names.

## Credentials in configs

YAML configs support ``${VAR}`` placeholders that resolve from the
process environment at load time (see ``substitute_env_vars`` in
``apibackuper.cmds.config_loader``). Recommended practice:

- Store API tokens, OAuth client secrets, and similar credentials in
  environment variables, not in the YAML file.
- Use ``${API_TOKEN}`` for required values (a clear error is raised
  when the variable is unset, naming the offending config field).
- Use ``${API_TOKEN:-default-value}`` only for non-sensitive defaults.
- Ensure the YAML config is not world-readable if it references any
  secrets inline.

A missing environment variable surfaces as a clear log message and
the project is not loaded — there is no silent fallback to an empty
string.

## Reporting vulnerabilities

Please report security issues to ivan@begtin.tech (or open a private
security advisory on GitHub). Do not file public issues for
non-disclosed vulnerabilities.
