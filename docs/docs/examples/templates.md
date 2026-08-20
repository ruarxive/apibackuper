---
title: "Templates"
description: "Starter YAML templates for common API shapes"
---
# Templates

Copy from `examples/templates/` and replace the example URLs.

## page-based.yaml

Page-number pagination:

```yaml
settings:
  name: page-based-example

project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page

params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100

data:
  data_key: items
  total_number_key: total

storage:
  storage_type: zip
```

## skip-offset.yaml

Offset / limit pagination. Set `iterate_by: skip`, `count_skip_param`, and
`page_size_param`.

## bearer-auth.yaml

Same as page-based, plus:

```yaml
auth:
  type: bearer
  token: "REPLACE_WITH_TOKEN"
```

Prefer `token_file` over an inline token.

## follow-multihop.yaml

List endpoint plus `follow.rules` for org → department → employee. See
[follow configuration](/configuration/follow).
