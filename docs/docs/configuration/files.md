---
title: "Files"
description: "Download files referenced by API records"
---
# Files

Used by [`apibackuper getfiles`](/commands/getfiles).

The record source must be a ZIP backup. `file_storage_type` selects the output
for downloaded files independently of that source requirement.

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
| `fetch_mode` | `prefix` concatenates `root_url` and the extracted value; `pattern` substitutes it into `{}` |
| `root_url` | URL prefix or pattern; use an empty prefix when record values are already complete URLs |
| `keys` | Comma-separated record keys that hold URLs or ids |
| `storage_mode` | Store by URL path (`filepath`) or by id |
| `file_storage_type` | `zip` (default) or `filesystem` |
| `use_aria2` | Queue downloads through a running aria2 RPC service; requires `aria2p` |

For an ID-based endpoint, for example:

```yaml
files:
  fetch_mode: pattern
  root_url: "https://files.example.com/documents/{}"
  keys: document_id
  storage_mode: id
  file_storage_type: filesystem
```

Built-in downloads use the project's authentication, headers, retries, SSL
verification, timeouts and rate limits. The aria2 integration connects to
`http://localhost:6800` with an empty RPC secret and queues files under
`storage/files/`; aria2 manages the transfers separately. Installing `aria2p`
alone does not start the RPC service or apply the built-in HTTP policy to it.

Discovered values are cached in `storage/allfiles.csv`. Remove that cache after
the source records change if you need to discover newly linked files. Existing
downloaded filenames are skipped when using the built-in downloader.
