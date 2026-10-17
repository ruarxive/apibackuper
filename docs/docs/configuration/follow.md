---
title: "Follow"
description: "Follow-up requests, URL patterns, and independent rules"
---
# Follow

Used by [`apibackuper follow`](/commands/follow).

## Single hop

```yaml
follow:
  follow_mode: item          # item | url | prefix
  follow_http_mode: GET
  follow_pattern: "https://api.example.com/items/{id}"
  follow_param: id
  follow_item_key: id
  follow_data_key: data
  follow_url_key: href
```

- `item` — format `follow_pattern` using record fields and `follow_param`
- `prefix` — append the record's `follow_item_key` value to `follow_pattern`
- `url` — use a URL already present on the record (`follow_pattern` unused)

`follow_item_key` must be present on every followed record. The current
orchestrator rejects `drilldown` even though the schema accepts that value.

## Multiple rules

```yaml
follow:
  rules:
    - name: profile
      follow_mode: item
      follow_pattern: "https://api.example.com/items/{id}"
      follow_item_key: id
      follow_param: id
    - name: events
      follow_mode: item
      follow_pattern: "https://api.example.com/items/{id}/events"
      follow_item_key: id
      follow_param: id
      follow_data_key: events
      iterate_by: page
      params:
        page_number_param: page
        page_size_param: per_page
        page_size_limit: 50
```

`follow` may also be a YAML list of the same rule objects.

Each rule reads the original backup pages independently. Results from one rule
are not passed to the next rule, so automatic multi-hop traversal is not
implemented. The existing `examples/templates/follow-multihop.yaml` demonstrates
the rule syntax; adapt its rules to the original records before use.

Named rules write `details_<name>.zip` archives beside the backup. An unnamed
rule writes `details.zip`, which is selected automatically by `export` when
present. Named rule archives are not automatically merged into that export.
