---
title: "Follow"
description: "Follow-up request configuration, including multi-hop rules"
---
# Follow

Used by [`apibackuper follow`](/commands/follow).

## Single hop

```yaml
follow:
  follow_mode: item          # item | url | drilldown | prefix
  follow_http_mode: GET
  follow_pattern: https://api.example.com/items/
  follow_param: id
  follow_item_key: id
  follow_data_key: data
  follow_url_key: href
```

- `item` — build a URL from `follow_pattern` + `follow_param`
- `url` — use a URL already present on the record (`follow_pattern` unused)

## Multi-hop rules

```yaml
follow:
  rules:
    - name: departments
      follow_mode: item
      follow_pattern: "https://api.example.com/orgs/{org_id}/departments"
      follow_item_key: id
      follow_param: org_id
      iterate_by: page
      params:
        page_number_param: page
        page_size_param: per_page
        page_size_limit: 50
    - name: employees
      follow_mode: item
      follow_pattern: "https://api.example.com/departments/{dept_id}/employees"
      follow_item_key: id
      follow_param: dept_id
```

`follow` may also be a YAML list of the same rule objects.

Template: `examples/templates/follow-multihop.yaml`.
