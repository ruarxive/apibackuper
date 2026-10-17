# Change: Fix critical bugs in core logic

## Why
Static analysis revealed several bugs in `apibackuper/cmds/project.py` that
cause incorrect behavior, crashes, or data corruption. These are silent
defects — not spec violations — that must be fixed to restore intended
behavior.

## What Changes
- Fix integer division bug in pagination page count calculation
- Remove dead no-op branch in start_page assignment
- Fix lexicographic string comparison for change-key values
- Fix URL query-character logic in `_url_replacer` non-query mode
- Add thread safety to parallel-execution shared counters
- Fix file handle leaks in `getfiles()` list/skipped files
- Fix malformed error message in `estimate()` duplicate request path

## Impact
- Affected specs: pagination, request-execution
- Affected code: `apibackuper/cmds/project.py`, `apibackuper/cmds/utils.py`
