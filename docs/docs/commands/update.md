---
title: "update"
description: "apibackuper update command reference"
---
# `update`

Re-fetches changed records using stored state and `data.change_key`.

```bash
apibackuper update
apibackuper update --resume -p myproject
```

**Key options:**

- `--resume` — continue from checkpoint
- `--projectpath` / `-p`
- `--verbose` / `-v`

Requires `project.update_mode` (default `by_change_key`) and a change key on
each record. See [incremental and update](/use-cases/incremental-and-update).
