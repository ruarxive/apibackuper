# Security Considerations

This document describes the security model of apibackuper and the risks you
should be aware of when running it.

## ⚠️ Config = executable code

apibackuper config files can reference arbitrary Python files via the
``code_postfetch`` and ``code_follow`` settings in the ``[code]`` section.
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

This is by design — apibackuper is a CLI tool for trusted local scripts —
but it must be **prominently documented** for users coming from
"innocent-looking YAML" mental models. See §S9 of the 2026-10 analysis
report.

## Hook context format

When ``[code.pre]``, ``[code.postfetch]`` or ``[code.follow]`` is set,
apibackuper writes a JSON blob to a temporary file and passes the path
to your script. The blob shape varies by hook:

### `before_run`

```json
{
  "mode": "full" | "incremental" | "update",
  "config": {...},
  "project_path": "/abs/path/to/project"
}
```

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
  "errors": {"503": 1}
}
```

## Credentials in logs

The ``apibackuper.log`` file written to your current working directory
captures request URLs and headers at DEBUG level. Authorization headers
and tokens are **redacted** (`***REDACTED***`) when the redact_* helpers
in ``apibackuper.cmds.utils`` are applied to the log payload. Do not
lower the log level to DEBUG on a production run unless you have
verified the redaction is in effect for your configuration.

## SSL/TLS verification

Set ``verify_ssl = false`` only for hosts with self-signed certificates.
When set to ``false`` apibackuper logs a warning (visible at INFO+).
You can also point ``verify_ssl`` at a CA-bundle path:

```ini
[request]
verify_ssl = /etc/ssl/certs/my-bundle.pem
```

## OAuth2 refresh

When using OAuth2 (``auth.type = oauth2``), the refresh token POST
honours the ``verify_ssl`` setting and a 30-second timeout by default.
Failures are logged at WARNING. Rotated refresh tokens are captured.

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