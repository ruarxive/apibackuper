## 1. Dead Code Removal
- [x] 1.1 Delete `apibackuper/cmds/http_client.py`
- [x] 1.2 Delete `tests/test_http_client.py` (tests dead code)
- [x] 1.3 Remove unused parameters from `create` command in `core.py`
- [x] 1.4 Remove unfinished `init()` method from CLI exposure
- [x] 1.5 Remove unfinished `to_package()` method from CLI exposure
- [x] 1.6 Remove empty `drilldown` follow mode stub
- [x] 1.7 Remove `custom_script` update mode stub
- [x] 1.8 Remove all commented-out code blocks in `project.py`

## 2. Deduplication
- [x] 2.1 Extract "config not found" error block into `_raise_config_not_found()` helper
- [x] 2.2 Replace all 8 occurrences of the block with the helper call
- [x] 2.3 Create `@_handle_cli_errors` decorator for CLI commands
- [x] 2.4 Apply decorator to all 6 commands in `core.py` with duplicated handlers
- [x] 2.5 Simplify individual command bodies to remove try/except boilerplate

## 3. Verification
- [x] 3.1 Confirm all existing tests pass after cleanup
- [x] 3.2 Remove any tests that reference deleted code
