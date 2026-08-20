---
title: "create"
description: "apibackuper create command reference"
---
# `create`

Creates a new project directory with a starter configuration file.

```bash
apibackuper create etrust
apibackuper create etrust --url https://api.example.com/items
```

**Arguments:**

- `name` — project directory name

**Key options:**

- `--url` / `-u` — API URL (stored for later editing; auto-init is limited)
- `--http-mode` / `-m` — `GET` or `POST` (default `GET`)
- `--iterateby` / `-b` — `page` or `number` (default `page`)
- `--work-modes` / `-w` — `full`, `incremental`, `update` (default `full`)
- `--pagekey` / `-k` — page/iteration parameter name
- `--pagesize` / `-s` — page size
- `--datakey` / `-d` — response field that holds items
- `--itemkey` / `-i` — unique item key (comma-separated for composites)
- `--changekey` / `-e` — change-detection field
- `--verbose` / `-v`

After create, edit `apibackuper.yaml` (and `params.json` for POST APIs), then
run [`estimate`](/commands/estimate) and [`run`](/commands/run).
