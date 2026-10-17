---
title: "Configuration"
description: "Build a project configuration from an API response, choose optional sections and validate the result"
slug: /configuration
---

# Configuration

A project describes one dataset: the endpoint to call, how to move between
pages, where records live in the response, and where to keep the archive.
Start with those four decisions, then add authentication, request limits or
follow-up work as needed.

## Files and loading order

The project directory is the directory passed with `-p` / `--projectpath`, or
otherwise the current directory. The first configuration file found wins:

1. `apibackuper.yaml`
2. `apibackuper.yml`
3. `apibackuper.cfg` — legacy INI; deprecated

Files are **not merged**. An old INI file does not supply missing sections in
a YAML configuration. Keep one authoritative file after migration. `create`
currently writes only a minimal INI scaffold; replace it with a complete YAML
file before collecting records.

A typical project looks like this:

```text
catalog/
  apibackuper.yaml         # endpoint, pagination, extraction and storage
  params.json              # optional fixed query parameters / POST body
  headers.json             # optional request headers
  url_params.json          # optional URL parameters for mixed/params modes
  follow_params.json       # optional parameters for detail requests
  hooks/                   # optional trusted Python scripts
  storage/                 # default location for ZIP and detail archives
  apibackuper_state.json   # generated successful-run state
  apibackuper_checkpoint.json  # generated recovery progress
```

These files have different path rules; see [path resolution](#path-resolution)
before running the same project from a scheduler or another directory.

## Map an API response to configuration

Suppose `GET https://api.example.com/items?page=1&per_page=2` returns:

```json
{
  "total": 3,
  "items": [
    {"id": 41, "title": "First item", "updated_at": "2026-01-01"},
    {"id": 42, "title": "Second item", "updated_at": "2026-01-02"}
  ]
}
```

The matching complete configuration is:

```yaml config
settings:
  name: catalog
project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 2
data:
  data_key: items
  total_number_key: total
  item_key: id
storage:
  storage_type: zip
  storage_path: storage
```

Replace the endpoint and field names with your API's actual contract. For a
working local endpoint, use the [five-record quick start](/getting-started/quick-start).

The configuration tells apibackuper to request pages 1 and 2, send `per_page=2`,
extract each response's `items`, and publish `storage/storage.zip`. The ZIP
contains page responses; `apibackuper export items.jsonl` extracts the records
into one object per line. `data.item_key` does not deduplicate those records.

The five top-level sections above are required. Optional sections add behavior:

| Need | Configure | Read next |
|------|-----------|-----------|
| Describe records, nested fields and update watermarks | `settings`, `project`, `data` | [Project and data](/configuration/project-and-data) |
| Walk pages, offsets or numeric ranges | `params` | [Pagination](/configuration/pagination) |
| Add fixed filters, headers or a POST body | JSON request files | [HTTP requests](/configuration/http-requests) |
| Supply credentials or refresh an access token | `auth` | [Authentication](/configuration/auth) |
| Set quotas, concurrency, retry policy and timeouts | `rate_limit`, `request`, `error_handling` | [Rate limiting and requests](/configuration/rate-limiting-and-requests) |
| Choose archive layout and recovery files | `storage` | [Storage](/configuration/storage) |
| Fetch detail endpoints for list records | `follow` | [Follow](/configuration/follow) |
| Download referenced attachments | `files` | [Files](/configuration/files) |
| Customize page requests or parse HTML | `hooks`, `code` | [Hooks](/configuration/hooks) |
| Filter/project the exported records | CLI `--where`, `--fields` | [Export filters](/configuration/export-filters) |

## Validate before fetching

```bash
apibackuper validate-config --strict -p catalog
apibackuper run full --dry-run -p catalog
apibackuper estimate full -p catalog
apibackuper run full -p catalog
```

Validation checks the YAML schema and selected project rules without HTTP.
Unknown YAML keys and invalid types fail validation. `--strict` also fails on
warnings. Dry-run prints the local execution plan and does not execute hooks.
It does not prove the endpoint, credentials, response keys or update filters work.

`estimate` contacts the API and requires a usable `total_number_key`. Backups
can use page-count metadata or short-page stopping without that field. Review
one actual response before starting a large collection.

## YAML values and environment variables

Use numbers for sizes and delays, `true`/`false` for booleans, and strings for
field paths and credentials. Quote dates when an API expects a string, and keep
keys at the documented nesting level:

```yaml
project:
  default_delay: 0.5
request:
  verify_ssl: true
  retry:
    max_retries: 3
auth:
  type: bearer
  token: "${API_TOKEN}"
```

YAML strings support `${VAR}` and `${VAR:-default}` from the process environment.
An unset/empty required variable stops loading. Defaults are suitable for
non-sensitive settings. Environment expansion does not apply to JSON request
files, and `.env` files are not loaded automatically.

Defaults in the schema are descriptive: leaving a field out uses the loader's
runtime fallback. It does not rewrite or populate the YAML. The
[reference](/configuration/reference) lists effective defaults and reserved options.

## Path resolution

| Path | Relative to |
|------|-------------|
| Configuration, request JSON files, `follow_params.json` | Project directory |
| `storage.storage_path` | Project directory; absolute paths are allowed |
| Default state and checkpoint files | Project directory |
| Explicit `settings.state_file` / `checkpoint_file` | Process working directory |
| `settings.logfile`, `auth.token_file`, `auth.password_file` | Process working directory |
| `hooks.*` | Project directory |
| Legacy `code.*` extraction paths | Call-site dependent; prefer absolute paths |
| CLI export filename | Process working directory |

Using `-p catalog` selects a project without changing the process working
directory. Use absolute credential/state paths for jobs launched from multiple
locations, and give independent projects separate storage and recovery files.

## Editing an existing project

Changing endpoint, filters, record shape or pagination can make existing pages
incompatible with a resumed run. Keep those settings fixed during recovery.
For a new dataset definition, use a new project or start a fresh full backup
after preserving any archive you need. Changing `storage_type` does not convert
an existing archive; see [storage migration](/configuration/storage#changing-backends-or-moving-a-project).

Before relying on update mode, configure the API's actual watermark parameter.
Merely declaring `work_modes: full,incremental,update` does not implement a
server-side change filter. See [update configuration](/configuration/project-and-data#configure-updates).
