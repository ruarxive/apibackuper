---
title: "When to use"
description: "Assess an API's pagination, authentication and consistency requirements before choosing a backup workflow"
---
# When to use apibackuper

apibackuper is a project-based CLI and Python library for retaining HTTP API
responses locally. It fits repeatable collection of paginated datasets where
you need saved pages, interruption recovery and exports for later analysis.

For example, a registry returning `items` and a total count through page/size
parameters can become a YAML project, a ZIP archive and a JSONL export. The
[Quick Start](/getting-started/quick-start) demonstrates that entire lifecycle
with five known records.

## Check the API contract first

| Question | Supported starting point | When to investigate further |
|----------|--------------------------|-----------------------------|
| How are requests made? | HTTP GET or read/query POST with JSON body | Another protocol, streaming, or write operations requiring transactions |
| How does pagination work? | Positive page numbers, numeric offsets, numeric from/to ranges, cursor tokens, next-page URLs or `Link` headers | Native zero-based page numbers, date-window iteration |
| What is returned? | JSON records, or XML parsed into a dictionary | HTML needs trusted extraction code; arbitrary binary responses are not record pages |
| How is access supplied? | Basic, Bearer, header API key, or compatible OAuth refresh | Browser login, interactive challenges, or another token-management contract |
| Can the source stay stable? | Fixed snapshot/version or stable ordering with reconciliation | Inserts/deletes continuously shift offset/page positions |
| How are changes exposed? | API-supported watermark filter and meaningful modification value | Changes/deletions cannot be queried reliably |

You do not need every optional feature to start. A public GET API with a known
page size is enough. Inspect one successful response and at least two different
pages before deciding a production collection is straightforward.

## Match the goal to the operation

| Goal | Operation | Result and boundary |
|------|-----------|---------------------|
| Retain a complete local collection | `run full` | New staged main backup; replaces the published one after success |
| Recover an interrupted full run | `run full --resume` | Continue its checkpointed staging data |
| Fill missing published pages | `run continue` | Skip existing flat page names; does not refresh saved records |
| Retain new/changed records | `update` | Append a generation using a saved filter bound when configured |
| Expand summary records | `follow full` | Fetch detail endpoints using explicit record IDs/URLs |
| Archive linked documents | `getfiles` | Extract references from a ZIP-backed collection and save bytes |
| Prepare analysis data | `export` | Extract/project/filter locally to JSONL, gzip, zstd or Parquet |
| Embed collection in a script | Python `ProjectBuilder` | Same project/storage concepts with programmatic calls |

`run incremental` is an alias for `run continue`, not a record-level change
query. Updates preserve historical versions; they do not automatically upsert
a current-object table. The API, not the `work_modes` declaration, must support
the change filter. See [incremental and update](/use-cases/incremental-and-update).

## What you retain

A project includes its YAML configuration, optional request files, stored pages,
successful state and recovery checkpoint. Choose ZIP, a filesystem directory
or SQLite page storage. Exports derive record-level files from those pages;
SQLite does not automatically create relational tables for API fields.

Full backups stage a replacement before publication. ZIP journals protect saved
pages during recovery. Retaining those files supports local continuation, but
does not create an independent disaster-recovery copy or a remote API snapshot.
See [storage](/configuration/storage) for layout and publication behavior.

Separate detail and attachment stages are useful when list responses omit
important fields. They occur later in time than the list collection, so they
do not imply a single consistent source snapshot. Named follow rules are
independent branches from original list records, not automatic multi-hop crawling.

## Decide what "backup" means for your dataset

Define the result before starting:

- A **full snapshot** needs a fixed source view or a documented collection interval,
  plus count/ID reconciliation.
- A **change history** needs a reliable filter, meaningful version values, retained
  generations and an explicit interpretation of deletion events.
- A **current-object view** needs downstream version selection and a tie-breaking
  policy; export itself preserves repeated IDs.
- A **document archive** needs verified file contents and unique destination names,
  not only a saved list of URLs.

A successful command means the pages required by its configured rules were saved.
It cannot prove that the API account had access to every object, that totals were
accurate, or that the source remained unchanged. Use
[backup completeness](/getting-started/data-integrity) to define the checks.

## When to use another approach

| Requirement | Suitable kind of workflow |
|-------------|---------------------------|
| Inspect one endpoint or debug a request | An HTTP client or a short request script |
| Consume GraphQL/gRPC/event streams or cursor-only pagination | A client that implements that protocol and continuation contract |
| Crawl websites and discover links recursively | A crawler with browser/HTML navigation support |
| Synchronize a warehouse with upserts and deletion handling | An ETL/replication pipeline with explicit destination semantics |
| Convert/query files already downloaded | A file-processing or analytical tool |
| Restore records into the original service | A service-specific import/restore workflow |

Custom hooks can adjust requests and trusted extraction code can transform
responses, but neither supplies general snapshot isolation, automatic schema
migration or an arbitrary protocol client. Prefer explicit, testable adaptations;
see [hooks](/configuration/hooks) before depending on them.

## A practical adoption check

Start with one small collection. Verify the first/last page, exported IDs and
representative fields. Exercise interruption/recovery with the same API contract,
then test one known modification if you need updates. Increase concurrency or
add detail/file collection only after that baseline is understood.

The tool has no built-in scheduler, retention pruning, distributed quota
coordination, restore-to-API command or latest-record deduplication. An external
job runner can launch it, but must provide credentials, prevent overlapping
writers and handle failure/recovery. These are workflow requirements to plan
around rather than options enabled by installing an extra.

Continue with [installation](/getting-started/installation),
[basic usage](/getting-started/basic-usage) for project paths, or the
[Cookbook](/getting-started/cookbook) for an existing project's next task.
