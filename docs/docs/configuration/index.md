---
title: "Configuration"
description: "YAML and INI project configuration overview"
slug: /configuration
---

# Configuration

apibackuper is configured per project. YAML is recommended. The loader looks
for `apibackuper.yaml` or `apibackuper.yml` first, then falls back to
`apibackuper.cfg`. INI is deprecated.

Validate after edits:

```bash
apibackuper validate-config
```

## Minimal YAML

```yaml
settings:
  initialized: true
  name: <name>

project:
  description: <description>
  url: <url>
  http_mode: GET
  work_modes: full,incremental,update
  iterate_by: page

params:
  page_size_param: <page size param>
  page_size_limit: 100
  page_number_param: page

data:
  total_number_key: total
  data_key: data
  item_key: id
  change_key: updated_at

storage:
  storage_type: zip
```

## Sections

| Section | Page |
|---------|------|
| `settings`, `project`, `data` | [Project and data](/configuration/project-and-data) |
| `params` | [Pagination](/configuration/pagination) |
| `auth` | [Authentication](/configuration/auth) |
| `rate_limit`, `request` | [Rate limiting and requests](/configuration/rate-limiting-and-requests) |
| `storage` | [Storage](/configuration/storage) |
| `follow` | [Follow](/configuration/follow) |
| `files` | [Files](/configuration/files) |
| `hooks`, `code` | [Hooks](/configuration/hooks) |
| All fields | [Reference](/configuration/reference) |

Starter files live in `examples/templates/`.
