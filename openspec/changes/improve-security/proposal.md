# Change: Improve security posture for SSL, credentials, and input handling

## Why
SSL certificate verification is unconditionally disabled (`verify=False`) in
`follow()` and `estimate()` code paths — over 20 hardcoded locations — with
no option to enable it. This exposes users to man-in-the-middle attacks.
Additionally, `FilesystemStorage` does not sanitize paths, enabling
directory traversal, and the `SqliteStorageBackend` uses f-string
interpolation for table names.

## What Changes
- Make SSL verification configurable in follow/estimate modes (default: enabled)
- Add `request.verify_ssl` config option (default `true`)
- Sanitize paths in `FilesystemBackend` to reject `..` traversal
- Use an allowlist for table names in `SqliteStorageBackend` queries
- Move plaintext credentials out of config files to environment variable references
- Add security documentation: how to use `.env` files, credential file permissions

## Impact
- Affected specs: security, request-execution, storage-backend
- Affected code: `apibackuper/cmds/project.py`, `apibackuper/storage/backends.py`,
  `apibackuper/auth.py`
