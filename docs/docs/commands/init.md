---
title: "init"
description: "apibackuper init command reference: create a complete project from one probed endpoint"
---
# `init`

Creates a project directory from an API endpoint. It sends one request, finds
the record list and count field, probes for the page, offset and page-size
parameters, and writes a complete `apibackuper.yaml`.

```bash
apibackuper init catalog --url "https://api.example.com/items?lang=en"
apibackuper init search --url https://api.example.com/search --method POST --body '{"q": "*"}'
apibackuper init private --url https://api.example.com/items --auth bearer --auth-env CATALOG_TOKEN
apibackuper init legacy --url https://api.example.com/items -H "Accept: application/json" --no-probe
```

**Arguments:**

- `path` — project directory to create

**Key options:**

- `--url` / `-u` — list or search endpoint (required)
- `--method` / `-m` — `GET` (default) or `POST`
- `--header` / `-H` — request header as `Name: value`; repeatable; saved to `headers.json`
- `--body` — JSON object sent as the POST body; saved to `params.json`
- `--auth` — `bearer`, `apikey` or `basic`; the secret is written as a `${VAR}` placeholder
- `--auth-env` — variable holding the secret (default `API_TOKEN`, `API_KEY` or `API_PASSWORD`)
- `--api-key-header` — header for `--auth apikey` (default `X-API-Key`)
- `--username` — user name for `--auth basic`
- `--data-key` — records path, when detection picks the wrong list
- `--no-probe` — write the files without sending requests
- `--force` — replace an existing configuration

GET query parameters move from the URL into `params.json`, except the detected
pagination parameters, which apibackuper sets on each page. Probing sends a few
extra requests, for example `page=2` and `per_page=100`, and accepts a parameter
only when the records change as expected. When the secret's variable is not
set, `init` writes the project without probing.

The command prints a JSON report:

```json
{
  "project_path": "/work/catalog",
  "detected": {
    "data_key": "items",
    "total_number_key": "total",
    "iterate_by": "page",
    "page_number_param": "page",
    "page_size_param": "per_page",
    "page_size_limit": 100
  },
  "records_on_first_page": 20,
  "fields": ["id", "title", "updated_at"],
  "sample_record": {"id": 1, "title": "Item 1", "updated_at": "2026-01-01"},
  "warnings": [],
  "valid": true,
  "next_steps": ["cd catalog", "apibackuper run full --max-pages 2", "apibackuper run full", "apibackuper export catalog.jsonl"]
}
```

Check `warnings` before a full run. Then confirm the configuration on real data
with [`run full --max-pages 2`](/commands/run#sample-run).
