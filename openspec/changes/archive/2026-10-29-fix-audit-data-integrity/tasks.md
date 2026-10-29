## 1. Audit findings
- [x] 1.1 Preserve old backups during full runs and resume (audit 1).
- [x] 1.2 Retain incremental update generations without overwrites (audit 2).
- [x] 1.3 Checkpoint only contiguous durable pages; never advance failed-run state (audit 3).
- [x] 1.4 Propagate failed/partial outcomes to nonzero CLI exits (audit 4).
- [x] 1.5 Support responses without data_key and normalize JSON/XML records (audit 5).
- [x] 1.6 Stop the entire parallel loop at end of data (audit 6).
- [x] 1.7 Construct flat query strings correctly, preserving existing queries (audit 7).
- [x] 1.8 Preserve typed YAML retry lists and validate execution settings (audit 8).
- [x] 1.9 Integrate filesystem backup, resume, update and export (audit 9).
- [x] 1.10 Unify HTTP success/retry/auth/timeout/rate handling across commands (audit 10).
- [x] 1.11 Redact URL, nested parameter and exception credentials (audit 11).
- [x] 1.12 Add real command lifecycle and failure regression tests; raise coverage floor (audit 12).
- [x] 1.13 Extract backup orchestration and remove duplicate pagination/progress/checkpoints (audit 13).
- [x] 1.14 Align Python metadata, CI, tox and pre-commit tool configuration (audit 14).
- [x] 1.15 Exclude tests from wheels; build/install/smoke-test packages on PRs (audit 15).
- [x] 1.16 Synchronize docs/examples and reconcile completed OpenSpec work (audit 16).

## 2. Acceptance
- [x] 2.1 Run focused regressions and full test suite, with coverage evidence.
- [x] 2.2 Pass formatting, lint, typing and security gates.
- [x] 2.3 Validate every YAML example and template against the bundled schema.
- [x] 2.4 Build sdist/wheel, check metadata and smoke-test the installed wheel.
- [x] 2.5 Pass strict OpenSpec validation and record implementation evidence.
