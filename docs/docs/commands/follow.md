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
```

**Arguments:**

- `mode` — `full` or `continue` (required)

Configure the `follow` section (single object or `rules` list). See
[follow configuration](/configuration/follow) and
[follow and files](/use-cases/follow-and-files).
