---
title: "info"
description: "apibackuper info command reference"
---
# `info`

Prints project parameters and storage statistics.

```bash
apibackuper info
apibackuper info -p hhemployers
apibackuper info --json -p hhemployers
```

`--json` writes a machine-readable report (useful for scripts and agents).

For the local Quick Start, selected report fields are:

```json
{
  "project": {"name": "local-demo"},
  "run": {"status": "success", "records_processed": 5, "last_page": 3},
  "statistics": {"storage": {"total_records": 5}}
}
```

The full report also includes configuration, request policy, authentication
type, storage and size information. `run` is absent before a successful state
exists. Its status describes saved successful state; a later interrupted run
can leave that state unchanged. Use the command exit status and checkpoint/logs
to assess the interrupted run. After [`verify`](/commands/verify), `verification`
holds its time and result until the next successful run. Counts include retained history rather than
distinct current IDs. See [backup completeness](/getting-started/data-integrity).
