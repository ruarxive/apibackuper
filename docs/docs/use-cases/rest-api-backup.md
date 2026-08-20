---
title: "REST API backup"
description: "Archive a paginated GET or POST API into local storage"
---
# REST API backup

The core workflow is: create a project, describe the endpoint, estimate, run,
export.

## Page-based GET API

Starter template: `examples/templates/page-based.yaml`.

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

```bash
apibackuper estimate full
apibackuper run full
apibackuper export items.jsonl
```

## Skip / offset APIs

Some APIs paginate with `offset` + `limit` instead of page numbers. Use
`iterate_by: skip` — see [pagination](/configuration/pagination) and
`examples/templates/skip-offset.yaml`.

## POST APIs

Set `http_mode: POST` and put the request body in `params.json` next to the
config. The [quick start](/getting-started/quick-start) uses this pattern for
e-trust.gosuslugi.ru.

## Working examples

The `examples/` directory includes real government and commercial APIs:

- **etrust** — POST API of Russian certificate authorities
- **hhemployers** — hh.ru employers
- **budgettofk**, **budgetreg**, **subsidies** — budget.gov.ru registries

See [Examples](/examples/).
