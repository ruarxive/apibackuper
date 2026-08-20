---
title: "Files"
description: "Download files referenced by API records"
---
# Files

Used by [`apibackuper getfiles`](/commands/getfiles).

```yaml
files:
  fetch_mode: prefix         # prefix | pattern
  root_url: https://files.example.com/
  keys: file_url,attachment
  default_ext: pdf
  storage_mode: filepath     # filepath | id
  file_storage_type: zip     # zip | filesystem
  use_aria2: false
```

| Field | Purpose |
|-------|---------|
| `fetch_mode` | `prefix` or `pattern` |
| `root_url` | Base URL for relative file paths |
| `keys` | Comma-separated record keys that hold URLs or ids |
| `storage_mode` | Store by URL path (`filepath`) or by id |
| `file_storage_type` | `zip` (default) or `filesystem` |
| `use_aria2` | Use aria2 when `aria2p` is installed |
