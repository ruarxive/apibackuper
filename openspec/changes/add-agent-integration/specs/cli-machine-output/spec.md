## ADDED Requirements

### Requirement: JSON output mode
The CLI SHALL accept a global `--json` option placed before the command. In
JSON mode each command SHALL write exactly one JSON object to stdout with `ok`,
`command` and, on success, `result`; all other output SHALL go to stderr. A
failing command SHALL write `ok: false`, an `error` object with a stable
`code`, the exception `type`, a `message` and a list of `hints` when known,
and the `exit_code`, and SHALL exit with that nonzero status. Without `--json`,
output SHALL remain unchanged.

#### Scenario: Successful command in JSON mode
- **WHEN** a user runs `apibackuper --json validate-config` on a valid project
- **THEN** stdout contains one JSON object with `ok: true` and the exit status is 0

#### Scenario: Missing configuration in JSON mode
- **WHEN** a user runs `apibackuper --json run full` in a directory without a configuration
- **THEN** stdout contains `{"ok": false, "error": {"code": "config_not_found", ...}}`
  and the exit status is nonzero

#### Scenario: Invalid option value in JSON mode
- **WHEN** a user runs `apibackuper --json run full --max-pages 0`
- **THEN** stdout contains an error with code `usage_error` and the exit status is 2

### Requirement: Progress output only on terminals
The CLI SHALL NOT draw progress bars when stderr, where they are drawn, is not
a terminal, or when the global `--no-progress` or `--json` option is given.
Summary lines SHALL still be written.

#### Scenario: Run captured by an agent
- **WHEN** `apibackuper run full` writes its output to a pipe
- **THEN** the output contains no progress bar redraws
