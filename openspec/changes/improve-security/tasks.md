## 1. SSL Configuration
- [x] 1.1 Add `request.verify_ssl` config option (default `true`) to config schema
- [x] 1.2 Replace all hardcoded `verify=False` in `follow()` with config-aware value
- [x] 1.3 Replace all hardcoded `verify=False` in `estimate()` with config-aware value
- [x] 1.4 Log a warning when SSL verification is disabled
- [x] 1.5 Add SSL verification to threaded/parallel request contexts

## 2. Path Traversal Prevention
- [x] 2.1 Add `_sanitize_path()` method to `FilesystemStorage`
- [x] 2.2 Reject paths containing `..` that escape base directory
- [x] 2.3 Add test for path traversal attempt

## 3. SQL Injection Prevention
- [x] 3.1 Replace f-string table name with allowlist validation in `SqliteStorageBackend`
- [x] 3.2 Raise `ValueError` for unrecognized table names
- [x] 3.3 Add test for SQL injection attempt via table name

## 4. Credential Management
- [ ] 4.1 Add environment variable substitution (`${VAR}`) in config loading
- [ ] 4.2 Report clear error when referenced variable is unset
- [ ] 4.3 Document credential best practices in README security section

## 5. Verification
- [x] 5.1 Add test for SSL verification enabled (mock certificate check)
- [x] 5.2 Add test for WARNING log when SSL disabled
- [x] 5.3 Confirm all existing tests still pass
