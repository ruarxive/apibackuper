---
title: "Pagination"
description: "Page, skip/offset, and range iteration"
---
# Pagination

`project.iterate_by` chooses how apibackuper walks the API.

## page

Page number + page size. Template: `examples/templates/page-based.yaml`.

```yaml
project:
  iterate_by: page

params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
  start_page: 1
```

## skip

Offset / limit. Template: `examples/templates/skip-offset.yaml`.

```yaml
project:
  iterate_by: skip

params:
  count_skip_param: offset
  page_size_param: limit
  page_size_limit: 200
```

## range

Inclusive numeric range using `count_from_param` and `count_to_param`.

## Other params

| Field | Purpose |
|-------|---------|
| `query_mode` | `query`, `params`, or `mixed` |
| `force_flat_params` | Flatten nested parameters |
| `change_key_param` | Request parameter for change-key filtering |
| `update_since_param` | Request parameter for update-since filtering |

If keys are unknown, try [`apibackuper detect`](/commands/detect).
