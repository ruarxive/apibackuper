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
```

**Arguments:**

- `mode` — `full` (default) or another configured work mode

**Key options:**

- `--resume` — continue from the last checkpoint
- `--projectpath` / `-p`
- `--verbose` / `-v`

INI configs print a deprecation warning; migrate to YAML.

Checkpoints are controlled by `settings.checkpoint_interval_pages` and
`settings.checkpoint_file`. See [incremental and update](/use-cases/incremental-and-update).
