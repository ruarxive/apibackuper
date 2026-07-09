# Change: Improve test suite quality and coverage

## Why
The test suite has 156 methods but provides false confidence. Twelve of
sixteen `test_core.py` tests assert `exit_code in [0, 1]` which always passes.
The core business logic in `ProjectBuilder` (3,369 lines) has only 17
superficial tests, and the `run()`, `follow()`, `update()`, and `export()`
methods are completely untested. Several tests mock everything and verify
only that a mock was called — tautologies that always pass.

## What Changes
- Rewrite `test_core.py` to assert specific outcomes, not `in [0, 1]`
- Add integration tests for `ProjectBuilder.run()` with mocked HTTP responses
- Add tests for pagination edge cases (non-divisible totals, zero pages)
- Add tests for retry logic and `Retry-After` header handling
- Add tests for export pipeline (JSONL, parquet, zstd formats)
- Add tests for `follow()` modes (item, url, prefix)
- Add negative tests: missing files, bad config, network errors, permission errors
- Add tests for `update()` incremental sync and checkpoint/resume
- Add rate limiter edge cases (zero limits, all-three-limits-active)
- Add storage tests: empty content, binary data, path traversal attempts

## Impact
- Affected specs: testing
- Affected code: `tests/test_core.py`, `tests/test_project.py`, new test files
