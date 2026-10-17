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
```

**Arguments:**

- `mode` — `full` (default), `continue`, or its alias `incremental`;
  use [`update`](/commands/update) for changed records

**Key options:**

- `--resume` — resume the selected mode using its existing pages and checkpoint
- `--dry-run` / `--profile` — print a JSON plan and local estimate without HTTP requests
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
`settings.checkpoint_file`. The interval controls periodic saves; the backup
workflow also saves at startup, after collection and during publication.
See [incremental and update](/use-cases/incremental-and-update).
