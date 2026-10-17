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

`create` writes a minimal legacy `apibackuper.cfg`. Save the following as a new
`apibackuper.yaml`; YAML takes precedence when both files exist:

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

## 2. Validate, preview and estimate

Check the configuration and preview the run without HTTP requests:

```bash
apibackuper validate-config
apibackuper run full --dry-run
```

Then sample the live API to estimate size and time:

```bash
apibackuper estimate full
```

Illustrative output (counts and timings depend on the API):

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

Records are staged in `storage/storage.zip.partial`. A successful full run
publishes `storage/storage.zip`; an incomplete run keeps any previous complete
backup. Continue an interrupted download with `apibackuper run full --resume`.

## 4. Export

Format is detected from the file extension, or you can pass `--format`:

```bash
apibackuper export etrust.jsonl
apibackuper export etrust.jsonl.gz
apibackuper export etrust.jsonl.zst
apibackuper export etrust.parquet
```

Parquet requires the optional `recommended` extra. JSON Lines, gzip and zstd
are available with the base installation. See [installation](/getting-started/installation).

## Next steps

- [Cookbook](/getting-started/cookbook) — task index by goal
- [Configuration](/configuration/) — YAML sections and field reference
- [Examples](/examples/) — working projects and templates
- [CLI reference](/commands/)
