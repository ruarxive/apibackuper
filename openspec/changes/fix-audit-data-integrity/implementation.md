# Implementation evidence

Implemented on 2026-10-16 following the user's explicit authorization to create
and execute the proposal. All sixteen audit findings and acceptance tasks are complete.

## Audit traceability

| Audit | Implementation | Regression evidence |
| --- | --- | --- |
| 1 | `storage/session.py`, `cmds/backup.py`: staged full backups and preserving resume | Full failure/resume lifecycle on ZIP, SQLite and filesystem; legacy checkpoints |
| 2 | Chronological update generations and generation-aware readers | Retained old/new records and export across all three backends |
| 3 | Runner contiguous boundary, unchanged failed-run state, durable publication intent | Middle-page failure, resumed generation, interrupted state commit, abrupt process exit |
| 4 | Shared request failures propagate to CLI errors | Actual CLI 403 failure exits 1; missing environment variable exits 2 |
| 5 | Shared normalized record extraction | Root JSON arrays, nonpaginated objects and XML pages |
| 6 | One ordered runner consumer for sequential and parallel execution | No later batch after terminal outcome; saved short page counted once |
| 7 | URL-aware query composition | Existing query and fragment; OAuth flat retry preserves actual URL |
| 8 | Typed YAML accessor, status-code normalization and schema consistency | Actual YAML retry list; fractional delays; invalid configuration preserves storage |
| 9 | Shared backend lifecycle/read interface | Filesystem backup/resume/update/export and nested generation restart |
| 10 | Shared HTTP execution for backup/follow/files/detection/estimate | Bounded transport/status retries, permanent403, auth, timeouts, HEAD/POST controls |
| 11 | Recursive values, URLs and exception diagnostics redacted | Logs/tracebacks omit dummy credentials; requests retain originals; OAuth error body redacted |
| 12 | Real storage workflows in `tests/test_backup_workflow.py` | Full test suite and 70% enforced coverage threshold |
| 13 | Extracted backup/follow/export workflows; reused fetch/page-count helpers | Same lifecycle tests plus helper suites; single owner of progress/checkpoint accounting |
| 14 | Python >=3.10; shared Black25.1.0, flake8, isort, mypy configuration | Formatter/lint/type checks and declared CI3.10–3.13 Ubuntu/macOS matrix |
| 15 | Restricted package discovery; PR artifact smoke job | Built/installed wheel outside source checkout; no test package; schema and CLI work |
| 16 | Version/support/recovery docs, valid examples, current base specs | Documentation build, 20 YAML examples/templates, strict OpenSpec validation |

Additional integrity regressions cover export source aliases, filesystem source
members, failed full follow, stale ZIP journals across full publication and
retrying failed ZIP compaction.

## Verification results

Local verification used macOS and Python3.13.7. Other supported versions and
Linux are configured in CI; their remote runs have not been observed here.

- Before implementation, the first four workflow regressions failed as expected.
- `python -m pytest --tb=short`: **519 passed**, no warnings, **73.19%** total
  coverage (audit baseline:448 passed,49% coverage).
- Backup workflow coverage84%; runner99%; ProjectBuilder53% (audit22%).
- `black --check apibackuper scripts`, `isort --check-only apibackuper scripts`,
  `flake8 apibackuper scripts` and `mypy apibackuper`: passed.
- `bandit -r apibackuper -ll`: passed, zero medium/high issues at this configured gate.
- `python -m scripts.validate_examples`: **20 configurations, zero invalid**.
- PEP517 sdist/wheel build and `twine check`: passed.
- `python scripts/check_wheel.py <wheel>`: passed after installation, with runtime
  dependencies, in a fresh isolated virtual environment outside the checkout.
- `npm run build` in `docs`: passed.
- `openspec validate --all --strict --no-interactive`: passed.
- `git diff --check`: passed.

## Compatibility and specification bookkeeping

Legacy flat pages and legacy checkpoints remain readable. Updates preserve
historical generations; exports intentionally include historical versions rather
than deduplicating object IDs. ZIP journal directories must accompany an archive
or staging archive until publication/recovery completes. Python3.8/3.9 support
was explicitly removed from metadata, tooling and documentation.

Five historical changes already marked complete were archived with
`--skip-specs` after their implemented requirements were reconciled into fifteen
base specifications. Unsupported multi-level follow chaining was not promoted
into current truth. Unfinished older proposals retain unchecked work; relevant
security/test task checkboxes were updated only where implementation evidence
exists. This audit change remains available for release review, with all tasks
checked; no publication or deployment is implied.
