---
title: "Cookbook"
description: "Task recipes with prerequisites, command order, expected results and links to complete API examples"
---
# Cookbook

Choose a recipe by the result you need. For a first run with known output,
complete the [five-record Quick Start](/getting-started/quick-start). For an
existing API, the recipes below assume a configured project named `catalog`
and commands run from its parent directory.

Replace `catalog` with your project path. Export filenames resolve from the
current working directory, not from `-p`. API-specific URLs, fields, sorting and
filters must match the service; example names are not universal defaults.

## Start a collection

### Check a project without contacting the API

Use after creating or editing YAML:

```bash
apibackuper validate-config --strict -p catalog
apibackuper run full --dry-run -p catalog
```

Expected result: validation succeeds without warnings, and the offline plan
shows your intended endpoint, pagination and storage. An unknown count can be
normal before a first backup. These commands cannot verify credentials, live
response fields or whether a server honors its filters.

Next: [configuration loading](/configuration/) and
[project/data fields](/configuration/project-and-data).

### Inspect an unfamiliar API

With a configured project and permission to make a live request:

```bash
apibackuper detect -p catalog
```

Review suggestions against a real response before using `--write-config`.
Detection does not establish the page-size cap, stable ordering or a reliable
change filter. For a URL-only starting point, see [`detect`](/commands/detect).

Next: [map a GET response to configuration](/use-cases/rest-api-backup).

### Run a first full backup

After local validation, and with usable total-count metadata for estimation:

```bash
apibackuper estimate full -p catalog
apibackuper run full -p catalog
apibackuper info --json -p catalog
apibackuper export catalog.jsonl -p catalog
```

Expected result: the main archive is published, saved state reports a successful
run and the export contains extracted records. Compare counts and distinct IDs
with the source. If the API has no usable record total, estimate cannot supply
that count; configure and verify its page-count/short-page behavior instead.

Next: [backup completeness](/getting-started/data-integrity).

### Send fixed filters, headers or a POST body

Add `params.json` or `headers.json` **inside** `catalog`. For a service supporting
these query values, a fixed parameter file could be:

```json
{"status": "active", "sort": "id"}
```

GET normally sends the parameters in the query; POST normally sends them as a
JSON body. Pagination overwrites the configured page/size fields per request.
Run validation and inspect a live sample after the edit. A changed dataset
scope needs a fresh collection rather than resuming incompatible saved pages.

Next: [HTTP request files](/configuration/http-requests) and
[POST walkthrough](/use-cases/post-api-backup).

## Recover or refresh an existing collection

### Resume an interrupted full backup

Keep its checkpoint, `.partial` storage and corresponding `.journal` sidecar.
After resolving the cause of failure:

```bash
apibackuper run full --resume -p catalog
```

Expected result: saved progress is reused and the first unresolved page is
retried, or pending publication is recovered. Use the same mode, storage path,
endpoint, filters and pagination. A completed checkpoint reports that the run
is already complete; use a fresh full run only when a new snapshot is intended.

Next: [run recovery](/commands/run) and
[resume troubleshooting](/getting-started/troubleshooting#resume-does-not-continue).

### Fill missing pages in a published archive

```bash
apibackuper run continue -p catalog
```

This starts at the first missing flat page name. The alias is `run incremental`.
It does not recover a full run's staging archive, recheck existing page contents
or query recently modified objects. Use it only when continuing the same stable
published page sequence is the intended operation.

Next: [choose a recovery command](/use-cases/incremental-and-update).

### Collect records changed since the successful baseline

First configure the API's actual change-key or timestamp request parameter.
Then:

```bash
apibackuper update --dry-run -p catalog
apibackuper update -p catalog
apibackuper export history.jsonl -p catalog
```

Expected result: a new retained generation with records returned for the saved
bound. Verify a known edit/new object before relying on the filter. Without a
watermark or matching API parameter, an update can request the full collection.
Repeated IDs remain in export.

If this update fails, recover **that update** rather than starting another one:

```bash
apibackuper update --resume -p catalog
```

Next: [change-key and timestamp examples](/use-cases/incremental-and-update) and
[current-object version selection](/use-cases/export-and-storage#5-build-a-current-object-view-from-history).

## Expand and deliver the data

### Fetch complete detail objects

After a successful list backup and a configured unnamed follow rule:

```bash
apibackuper follow full --dry-run -p catalog
apibackuper follow full -p catalog
apibackuper export details.jsonl -p catalog
```

Expected result: an unnamed `details.zip`; normal export then selects its
records using `follow_data_key`. Save a list export before the first follow if
you need both representations. For interruption recovery, use `follow continue`;
it skips saved detail names rather than refetching them.

Next: [follow and files](/use-cases/follow-and-files).

### Download linked documents

Requires ZIP main storage, a `files` section and a completed source collection:

```bash
apibackuper getfiles -p catalog
```

With follow configured, the source is unnamed `details.zip`. Otherwise references
come from main pages. Verify expected filenames/content after download. A later
invocation reuses `allfiles.csv` and skips saved names; refresh discovery after
updating source records. Clearing the cache alone does not replace changed bytes
at an existing filename.

Next: [file discovery and refresh](/configuration/files#download-inventory-and-discovery-cache).

### Produce a filtered or compressed export

For numeric IDs and fields present in your saved records:

```bash
apibackuper export selected.jsonl --fields id,title --where "id >= 3" -p catalog
apibackuper export catalog.jsonl.gz -p catalog
apibackuper export catalog.jsonl.zst -p catalog
```

Export is local and preserves history. `.json` also means JSON Lines; Parquet
requires the optional extra. `--where` supports one comparison and does not parse
SQL, compound conditions or dates. Keep output outside source backup paths.

Next: [filter grammar](/configuration/export-filters) and
[export verification](/use-cases/export-and-storage).

## Prepare a protected or recurring job

### Add authentication and stay within a quota

Configure `auth`, `rate_limit` and active connection/read timeouts. Supply secrets
through the environment or supported credential files; `.env` is not automatic.
Start with one page worker and verify the account's scope through a live sample.
An offline plan does not test access or guarantee that the account sees every
record.

Next: [protected API workflow](/use-cases/protected-apis), including token
replacement, OAuth refresh and per-process quota limits.

### Embed the project or schedule a command

For Python integration, use the [Python API](/development/python-api). For a
recurring CLI job, use an external scheduler with a fixed environment/project
path, credentials, one writer and exit-status handling. Recover unfinished work
before starting another update; do not export unfinished update history as a
verified result.

Next: [best practices](/getting-started/best-practices) for operation and
[troubleshooting](/getting-started/troubleshooting) when an invocation fails.
