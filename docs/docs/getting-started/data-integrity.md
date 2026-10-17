---
title: "Backup completeness"
description: "Pagination boundaries, changing datasets, update history and verification"
---
# Backup completeness

A successful run means the required pages were saved and publication completed
under the configured pagination rules. It does not prove the API returned every
object or provided a snapshot at one instant. A durable archive can still be
incomplete if its pagination or response keys were configured incorrectly.

## How collection ends

- `data.total_number_key` determines the page count as `ceil(total / page_size_limit)`.
- If no usable record count exists, `data.pages_number_key` can provide a page count.
- Without either usable count, the runner falls back to at most **20,000 pages**.
- A list page shorter than `page_size_limit`, including an empty list, ends
  collection early. Configure the actual page size returned by the service;
  a server that silently caps 100 requested records to 50 can cause early termination.
- A bare single-object response ends collection after that object.

Parallel requests may already be in flight when an end page is encountered.
The ordered runner stops collection at that boundary. Missing pages and exhausted
retries cause a nonzero exit; reaching a configured/fallback boundary is not
proof that no later API records exist.

`start_page` defaults to 1 and must be positive. Native zero-based page numbers,
cursor tokens, next-link traversal and streaming APIs are not implemented.
Skip pagination computes offset `(page - 1) * page_size_limit`.
[Pagination](/configuration/pagination) documents range boundaries and examples.

## APIs that change during collection

Request stable sorting by a unique, immutable key using the API's own sort
parameter in `params.json`. Inserts and deletes can move records between
page/offset positions, causing gaps or repeated IDs even in a successful run.
Changing `parallelism` does not create snapshot isolation.

When available, use an API snapshot token, a fixed export version or a bounded
query interval. Keep those fixed across resume. If the API cannot provide a
stable view, document the collection interval and reconcile IDs/counts afterward.
Avoid changing endpoint, filters, pagination, extraction code or authentication scope
while resuming an interrupted run; start a fresh full backup when the dataset
definition changes.

## Updates and deleted objects

`update` sends the last successful watermark through the configured API filter.
The API determines inclusive/exclusive boundary semantics and timestamp precision.
For timestamp mode the watermark comes from the prior run's start time;
verify that the API accepts its ISO timestamp representation and timezone.
Late or backdated changes require API-specific reconciliation or periodic full runs.

Each update retains a generation. Export includes all retained records, including
repeated IDs. It neither removes previously archived objects that disappear from
the API nor infers deletion tombstones. If the API emits deletion events, retain
and interpret them downstream. A latest-object view requires a deterministic
version field and tie-breaking policy; arbitrary export order is insufficient.

## Verify and retain a backup

1. Check the command's exit status, logs, and `apibackuper info --json`.
2. Export JSONL and compare record and distinct-ID counts with the source's
   known count, allowing for retained update history.
3. Check first/last IDs, date boundaries and representative nested fields.
4. Compare consecutive collection results to detect unexpected drops or gaps.
5. Keep project configuration and extraction scripts with the archive, successful
   state and checkpoints. Preserve `.partial` and `.journal` recovery files until
   recovery completes, as described under [run](/commands/run).

There is no automatic retention pruning or archive restore-to-API command.
Updates grow storage over time. For rotation, stop writers, create and verify a
fresh full backup, then retain or move the old archive together with its state
and configuration according to your policy. Avoid editing `runs/` members or
checkpoints manually. Schedule jobs without overlapping writers to the same
project or storage path.
