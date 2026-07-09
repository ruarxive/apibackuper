# Change: Remove dead code and eliminate duplication

## Why
The codebase contains a fully implemented but never-used `HTTPClient` class,
multiple copy-pasted error-handling blocks, and several unfinished methods
exposed in the CLI. This dead code mislead contributors, inflates the
maintenance surface, and creates a false sense of test coverage.

## What Changes
- Delete `apibackuper/cmds/http_client.py` (dead code, logic duplicated in `project.py`)
- Extract the 8x-duplicated "config not found" error block into a single helper
- Extract the 6x-duplicated CLI error-handling pattern in `core.py` into a decorator
- Remove unused parameters from the `create` command
- Remove unfinished `init()` and `to_package()` methods from CLI exposure
- Remove empty `drilldown` follow mode and `custom_script` update mode stubs
- Remove commented-out code blocks throughout `project.py`

## Impact
- Affected specs: code-quality, request-execution
- Affected code: `apibackuper/cmds/http_client.py`, `apibackuper/cmds/project.py`,
  `apibackuper/core.py`
