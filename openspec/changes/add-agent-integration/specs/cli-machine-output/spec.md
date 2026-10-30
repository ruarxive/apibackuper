## ADDED Requirements

### Requirement: JSON output mode
The CLI SHALL accept a global `--json` option. In JSON mode each command SHALL
write exactly one JSON object to stdout describing its result, and a failing
command SHALL write a JSON object with `ok: false`, a stable `error.code`, an
`error.message` and an `error.hint` before exiting with a nonzero status.
Without `--json`, output SHALL remain unchanged.

#### Scenario: Successful command in JSON mode
- **WHEN** a user runs `apibackuper --json validate-config` on a valid project
- **THEN** stdout contains one JSON object with `ok: true` and the exit status is 0

#### Scenario: Missing configuration in JSON mode
- **WHEN** a user runs `apibackuper --json run full` in a directory without a configuration
- **THEN** stdout contains `{"ok": false, "error": {"code": "config_not_found", ...}}`
  and the exit status is nonzero

### Requirement: Progress output only on terminals
The CLI SHALL NOT draw progress bars when stdout is not a terminal or when
`--no-progress` or `--json` is given. Summary lines SHALL still be written.

#### Scenario: Run captured by an agent
- **WHEN** `apibackuper run full` writes to a pipe
- **THEN** the output contains no progress bar redraws
