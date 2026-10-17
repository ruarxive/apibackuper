---
title: "follow"
description: "apibackuper follow command reference"
---
# `follow`

Issues follow-up requests for records already stored by `run`.

```bash
apibackuper follow full
apibackuper follow continue
apibackuper follow continue -p myproject
apibackuper follow full --dry-run
```

**Arguments:**

- `mode` — `full` or `continue` (required)

**Key options:**

- `--dry-run` — print the plan and local estimate without HTTP requests
- `--projectpath` / `-p` — project directory

Configure the `follow` section (single object or `rules` list). See
[follow configuration](/configuration/follow) and
[follow and files](/use-cases/follow-and-files).

Full runs stage detail archives in `.partial` storage and publish them after
success. `follow continue` reuses saved detail objects, including an interrupted
full run's staging archive. Keep any ZIP `.journal` sidecar with its archive.
