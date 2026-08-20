---
title: "getfiles"
description: "apibackuper getfiles command reference"
---
# `getfiles`

Downloads files referenced by stored records.

```bash
apibackuper getfiles
apibackuper getfiles -p myproject
```

Requires a `files` section:

```yaml
files:
  fetch_mode: prefix
  root_url: https://files.example.com/
  keys: file_url
  storage_mode: filepath
```

See [files configuration](/configuration/files).
