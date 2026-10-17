## Context
The current runner duplicates counters and checkpoints with ProjectBuilder,
classifies errors by retryability, and opens full backups destructively before
the first request. SQLite updates replace page names and ZIP updates append
duplicate names. Extracted request/page-count helpers are not consistently used.

## Decisions
- Stage a fresh full backup beside its destination; publish after closing it
  successfully. Resume opens the checkpoint's existing staging or legacy archive
  without resetting it. Failed runs retain staging and the previous complete backup.
- Journal ZIP members durably beside the archive and compact by atomic replacement on close; a process crash cannot destroy its central directory. Compact any old destination journal before publishing a replacement full ZIP.
- Persist publication intent and pending state before replacing archives, so state-write or checkpoint-write interruptions recover without HTTP.
- Give updates a chronological unique run prefix. Readers enumerate legacy flat pages and new
  generation pages. Re-saving the same logical member replaces it idempotently.
- Keep state unchanged after any failed page. Persist next_page at the first
  unsaved gap, never beyond it; reuse the same generation when resuming.
- Let runner own page outcomes, progress and checkpoints. Return structured
  completion metadata while retaining the legacy error-count mapping interface.
- Move the backup workflow into cmds/backup.py; retain ProjectBuilder.run/update
  as public facades. Reuse build_page_request, parse_total_pages and record extraction.
- Use one HTTP execution path, including follow/files. Distinguish successful
  status codes from retryable failures; retry transport errors within a bounded budget.
- Preserve ConfigParser-compatible string access and add typed YAML access where
  required. Reject invalid execution configurations before changing storage.
- Declare Python >=3.10, centralize tool configuration and build/install wheels
  on pull requests. Keep tests outside wheels and schemas inside them.

## Compatibility and Rollback
Existing storage.zip/storage.db and page_N.json names remain readable. Old
checkpoints without next_page replay last_page safely. Update generations retain
all old data; no destructive migration is performed. Rolling back code leaves
legacy archives usable; new namespaced generations require the updated readers.
The Python floor change is explicit in metadata, documentation and changelog.

## Verification
Run regression cases before fixes, then the complete suite, formatting, lint,
type checks, security checks, strict OpenSpec validation, example validation,
source/wheel builds and installed-wheel CLI/schema checks. No live API is required.
