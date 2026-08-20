---
title: "Quick Start"
description: "Create a project, estimate size, run a backup, and export data"
---
# Quick Start

Short path to a first successful backup. Not sure where to start? Pick your
goal in the [cookbook](/getting-started/cookbook).

This example archives the list of Russian certificate authorities published at
e-trust.gosuslugi.ru through an undocumented POST API.

## 1. Create a project

```bash
apibackuper create etrust
cd etrust
```

Edit `apibackuper.yaml`:

```yaml
settings:
  initialized: true
  name: etrust

project:
  description: E-Trust UC list
  url: https://e-trust.gosuslugi.ru/app/scc/portal/api/v1/portal/ca/list
  http_mode: POST
  work_modes: full,incremental,update
  iterate_by: page

params:
  page_size_param: recordsOnPage
  page_size_limit: 100
  page_number_param: page

data:
  total_number_key: total
  data_key: data
  item_key: РеестровыйНомер
  change_key: СтатусАккредитации.ДействуетС

storage:
  storage_type: zip
```

Add `params.json` with the POST body used for each request:

```json
{
  "page": 1,
  "orderBy": "id",
  "ascending": false,
  "recordsOnPage": 100,
  "searchString": null,
  "cities": null,
  "software": null,
  "cryptToolClasses": null,
  "statuses": null
}
```

## 2. Estimate size and time

```bash
apibackuper estimate full
```

Typical output:

```text
Total records: 502
Records per request: 100
Total requests: 6
Average record size 32277.96 bytes
Estimated size (json lines) 16.20 MB
Avg request time, seconds 66.9260
Estimated all requests time, seconds 402.8947
```

## 3. Run the backup

```bash
apibackuper run full
```

Records are stored in the project storage (by default a ZIP file).

## 4. Export

Format is detected from the file extension, or you can pass `--format`:

```bash
apibackuper export etrust.jsonl
apibackuper export etrust.jsonl.gz
apibackuper export etrust.jsonl.zst
apibackuper export etrust.parquet
```

## Next steps

- [Cookbook](/getting-started/cookbook) — task index by goal
- [Configuration](/configuration/) — YAML sections and field reference
- [Examples](/examples/) — working projects and templates
- [CLI reference](/commands/)
