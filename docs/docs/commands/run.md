---
title: "run"
description: "apibackuper run command reference"
---
# `run`

Executes the project and stores API records in local storage.

```bash
apibackuper run full
apibackuper run full -p budgettofk
apibackuper run full --resume
apibackuper run continue
apibackuper run full --dry-run
apibackuper run full --max-pages 2
```

**Arguments:**

- `mode` — `full` (default), `continue`, or its alias `incremental`;
  use [`update`](/commands/update) for changed records

**Key options:**

- `--resume` — resume the selected mode using its existing pages and checkpoint
- `--dry-run` / `--profile` — print a JSON plan, local estimate and configuration warnings without HTTP requests
- `--max-pages N` — [sample run](#sample-run) of at most N pages
- `--projectpath` / `-p`
- `--verbose` / `-v`

INI configs print a deprecation warning; migrate to YAML.

`run continue` (alias `run incremental`) scans existing published pages and
starts at the first missing page. Use `run full --resume` to recover a full
backup in `.partial` storage. `--resume` requires a valid checkpoint for the
same mode and storage path; a completed checkpoint reports that the backup is
already complete.

The dry-run estimate uses saved state and configured limits. For an estimate
based on a live sample response, use [`estimate`](/commands/estimate).

## Sample run

`run full --max-pages N` fetches at most N pages with the project's
configuration into a temporary archive, prints a JSON summary and deletes the
archive. The project's storage, state and checkpoint stay unchanged, and the
`after_run` hook does not run.

```json
{
  "pages": 2,
  "records": 4,
  "total_reported": 5,
  "more_pages": true,
  "fields": ["id", "title", "updated_at"],
  "preview": [{"id": 1, "title": "Item 1", "updated_at": "2026-01-01"}],
  "warnings": []
}
```

The same checks as a full run apply, so two pages are enough to catch an API
that ignores the pagination parameter or caps the page size below
`page_size_limit`. `--max-pages` works only with `run full` without `--resume`.

## Full backups and failures

`run full` writes to a sibling staging path ending in `.partial`, such as
`storage.zip.partial`. The previous complete archive remains available until the
new full backup has saved all required pages and is ready to replace it. A failed
or incomplete backup returns a nonzero exit status, keeps the last successful
state unchanged, and retains its staging data for recovery.

Resume the interrupted run with the same project and mode:

```bash
apibackuper run full --resume
```

Saved pages are preserved. The checkpoint advances only through a contiguous
sequence of durably saved pages, and resume starts at the first unresolved page.
Legacy flat archives and checkpoints remain readable; a checkpoint without
`next_page` safely replays its last recorded page.

## ZIP recovery files

The ZIP backend saves pages durably in a `.journal` sidecar directory before
advancing a checkpoint. For example, a full run can have both
`storage.zip.partial` and `storage.zip.partial.journal`. Opening the archive for
resume automatically reads journal pages; closing it compacts them into the ZIP
and removes the journal after successful compaction.

Keep the checkpoint, archive or `.partial` path, and its corresponding `.journal`
directory together during recovery. A journal left after an abrupt interruption
can contain saved pages that have not yet been compacted into the ZIP.

If interruption occurs after downloading has finished, a checkpoint can contain
a pending publication intent. `--resume` completes publication and state recovery
from the saved data, which may require no further HTTP requests.

Checkpoints are controlled by `settings.checkpoint_interval_pages` and
`settings.checkpoint_file`. The interval (default: every page) controls periodic
saves; the backup workflow also saves at startup, after collection, during
publication and when collection is interrupted.
See [incremental and update](/use-cases/incremental-and-update).
