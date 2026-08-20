---
title: "Cookbook"
description: "Pick a goal, then follow verified apibackuper commands"
---
# Cookbook

apibackuper covers several backup workflows. This page is a task-oriented
index: find the row that sounds like you, then follow the linked sections.
If you are completely new, do the [quick start](/getting-started/quick-start)
first.

| You want to… | Start with |
|--------------|------------|
| Archive a paginated public API | [Quick start](/getting-started/quick-start), [`run`](/commands/run) |
| Guess pagination keys from a live URL | [`detect`](/commands/detect) |
| Estimate size before a long run | [`estimate`](/commands/estimate) |
| Resume a stopped job | [`run --resume`](/commands/run), [best practices](/getting-started/best-practices) |
| Fetch only changed records | [`update`](/commands/update), [incremental and update](/use-cases/incremental-and-update) |
| Follow list items into detail endpoints | [`follow`](/commands/follow), [follow and files](/use-cases/follow-and-files) |
| Download files attached to records | [`getfiles`](/commands/getfiles) |
| Export JSONL, gzip, zstd, or Parquet | [`export`](/commands/export) |
| Authenticate against a protected API | [Authentication](/configuration/auth), [protected APIs](/use-cases/protected-apis) |
| Stay under API rate limits | [Rate limiting](/configuration/rate-limiting-and-requests) |
| Disable SSL verification for a broken cert | [Troubleshooting](/getting-started/troubleshooting) |
| Customize requests with Python | [Hooks](/configuration/hooks) |

## Detailed walkthroughs

- [REST API backup](/use-cases/rest-api-backup)
- [Incremental and update](/use-cases/incremental-and-update)
- [Follow and files](/use-cases/follow-and-files)
- [Export and storage](/use-cases/export-and-storage)
- [Protected APIs](/use-cases/protected-apis)
