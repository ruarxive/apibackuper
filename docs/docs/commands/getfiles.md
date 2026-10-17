---
title: "getfiles"
description: "apibackuper getfiles command reference"
---
# `getfiles`

Downloads files referenced by records in a ZIP backup. The source backup must
use `storage.storage_type: zip`; the downloaded files themselves may be stored
in ZIP or filesystem storage.

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

If a `follow` section is configured, URLs are extracted from `details.zip`;
otherwise they are read from the backup pages. Named follow rule archives
are not selected automatically. Complete the corresponding backup/follow run
before downloading files.

The command caches discovered URLs or IDs in `storage/allfiles.csv` and skips
already stored filenames on later invocations. To discover new attachments
after updating the source records, remove that cache before running `getfiles`
again. The default output is `storage/files.zip`; filesystem output is
`storage/files/`.
