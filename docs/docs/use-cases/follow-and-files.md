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
  follow_pattern: https://api.example.com/items/
  follow_param: id
  follow_item_key: id
```

`follow_mode` can be `item`, `url`, `drilldown`, or `prefix`. If mode is `url`,
`follow_pattern` is unused and the URL is taken from the record.

## Multi-hop follow

Use `follow.rules` for org → department → employee style walks. See
`examples/templates/follow-multihop.yaml` and
[follow configuration](/configuration/follow).

## Download files

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
