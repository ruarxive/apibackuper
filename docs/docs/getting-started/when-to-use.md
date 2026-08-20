---
title: "When to use"
description: "When apibackuper is the right tool, and when it is not"
---
# When to use apibackuper

**apibackuper is a project-based CLI for archiving paginated REST APIs** into
local storage. It is built for long-running, repeatable backups rather than
one-off HTTP requests.

| Need | Prefer |
|------|--------|
| Download every page of a REST API into a local archive | **apibackuper** |
| Resume, update, or incrementally refresh an existing archive | **apibackuper** |
| Follow list endpoints into detail endpoints, then download files | **apibackuper** |
| One-off HTTP requests or API exploration | **curl**, **httpie**, **Postman** |
| Transform already-downloaded JSONL/CSV/Parquet files | **[undatum](https://github.com/datenoio/undatum)** |
| Crawl HTML websites | a web crawler, not apibackuper |
| GraphQL, gRPC, or streaming APIs | a specialized client |

## Strengths

- YAML (recommended) or INI project configuration
- Page, skip/offset, and range pagination
- Full, incremental, and update work modes
- ZIP, filesystem, or SQLite storage
- Export to JSON Lines, gzip, zstd, or Parquet
- Basic, Bearer, API Key, and OAuth2 authentication
- Rate limiting, retries, concurrency, and SSL controls
- Follow-up requests and associated file downloads
- Optional Python hooks for custom pipeline steps

## When another tool wins

- **curl / httpie**: a single request or a tiny script
- **undatum**: converting, querying, or validating files you already have
- **Airbyte / custom ETL**: warehouse-oriented sync with connectors and dbt
- **wget / aria2**: bulk file download when you already have a URL list

## Related docs

- [Quick start](/getting-started/quick-start)
- [Cookbook](/getting-started/cookbook)
- [REST API backup](/use-cases/rest-api-backup)
