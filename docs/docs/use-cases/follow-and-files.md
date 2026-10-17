---
title: "Follow and files"
description: "Walk from list endpoints to detail objects and download attached files"
---
# Follow and files

Many APIs expose a list endpoint first, then a detail URL per item. apibackuper
can follow those links and optionally download files referenced by each record.

## Follow list items

After a successful `run`, collect details:

```bash
apibackuper follow full
# or continue an interrupted follow
apibackuper follow continue
```

Single-hop config:

```yaml
follow:
  follow_mode: item
  follow_pattern: "https://api.example.com/items/{id}"
  follow_param: id
  follow_item_key: id
```

`follow_mode` can be `item`, `url`, or `prefix`. If mode is `url`,
`follow_pattern` is unused and the URL is taken from the record.

## Multiple follow rules

Use `follow.rules` for independent requests based on the original list records.
Each named rule stores its own `details_<name>.zip`; rules do not consume the
previous rule's output. Automatic org → department → employee traversal is
not implemented. See [follow configuration](/configuration/follow) for examples.

## Download files

`getfiles` currently requires a ZIP source backup. Downloaded files can use ZIP
or filesystem output; see [files configuration](/configuration/files).

```yaml
files:
  fetch_mode: prefix
  root_url: https://files.example.com/
  keys: file_url,attachment
  storage_mode: filepath
```

```bash
apibackuper getfiles
```

Files are stored in `storage/files.zip` (or a filesystem tree). Enable
`use_aria2: true` when `aria2p` is installed for faster downloads.
