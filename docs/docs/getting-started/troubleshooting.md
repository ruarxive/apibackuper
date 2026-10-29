---
title: "Troubleshooting"
description: "Diagnose failures by stage, inspect paths and HTTP behavior, and recover without discarding saved progress"
---
# Troubleshooting

Start with the failing command and its latest exit status. Preserve saved
archives, checkpoints and recovery sidecars while investigating. `info` describes
saved successful state and can still show an earlier success after a later run
fails; a file on disk is not enough to establish that the latest collection
completed.

## Locate the failing stage

| Stage | First check | Network? |
|-------|-------------|----------|
| Installation/command startup | `python -m apibackuper --help` | No API request |
| Configuration | `apibackuper validate-config --strict` | Offline |
| Execution plan | `apibackuper run full --dry-run` | Offline |
| Endpoint/permissions/response | `apibackuper estimate full` with valid total metadata | Live sample |
| Page collection | Latest `run`/`update` exit status and log | Live requests |
| Export | Saved source, extraction key, filter and output path | Offline |
| Details/files | Source stage finished and matching configuration present | Live follow/download requests |

The default log is `apibackuper.log` in the **process working directory**.
`settings.logfile` can select another path. `--verbose` adds console logging on
`create`, `detect`, `run`, `update`, `export` and `validate-config`; it is not a
universal flag. Use `<command> --help` for its supported options.

Record the exact command, working directory, package version (`python -m pip show
apibackuper`), config format and first relevant error before changing settings.
Change one cause at a time and validate again.

## Command or module not found

If `apibackuper` is missing but this works:

```bash
python -m apibackuper --help
```

reactivate the environment that installed it or use module invocation. If the
module is also missing, run `python -m pip show apibackuper` with that interpreter
and install into the intended environment. A dependency installed in another
Python/tool-manager environment is not available to this CLI. See
[installation](/getting-started/installation).

## Configuration not found or edits have no effect

Select the project explicitly from its parent directory:

```bash
apibackuper validate-config --strict -p catalog
apibackuper run full --dry-run -p catalog
```

Check the directory and exact filenames. The loader tries `apibackuper.yaml`,
then `apibackuper.yml`, then legacy `apibackuper.cfg`; it does not merge them.
An old YAML file can mask edits to INI. `create` supplies a minimal INI scaffold,
so a new project still needs an actual API definition.

YAML indentation, unknown keys and wrong value types fail validation. Fix the
reported path rather than moving options arbitrarily between sections. An INI
deprecation warning also makes `--strict` fail; migrate to a complete YAML
configuration rather than hiding the warning.

## Unresolved environment variable or rejected credential

`${API_TOKEN}` must be non-empty in the environment launching the process.
A `.env` file is not loaded automatically. Expansion applies to YAML strings,
not request JSON files.

For file-backed credentials, check the absolute path, readable/non-empty content
and whether an inline value overrides the file. The file contains just the
credential, without a `Bearer ` prefix or JSON wrapper. Changes to the file do
not update a running process; launch a new command with the current credential.

HTTP 401 usually requires checking credential value/expiry and any supported
refresh contract. HTTP 403 requires checking permissions, scope and endpoint
policy; OAuth refresh is triggered by 401, not 403. A successful dry-run has not
tested access. See [authentication](/configuration/auth) and
[protected APIs](/use-cases/protected-apis).

## Connection refused, timeout or TLS failure

For the local walkthrough, check that the server terminal is still running and
its port matches `project.url`. `127.0.0.1` refers to the machine/process network
environment running the CLI; a server on another host/container needs appropriate
routing rather than the same loopback URL.

For a real API, inspect the endpoint, network/proxy environment and error before
changing timeouts. The active fields are:

```yaml
request:
  connect_timeout: 10
  read_timeout: 120
  verify_ssl: true
```

The legacy `request.timeout` does not replace the connection/read pair. Read
timeout bounds waits for data, not total collection duration. A longer timeout
does not solve a wrong URL, rejected credentials or an unavailable service.

Keep SSL verification enabled while correcting endpoint/trust/proxy problems.
For an explicitly trusted internal/test endpoint where verification is deliberately
disabled, `request.verify_ssl: false` is supported and logs a warning. The option
is boolean, not a CA-bundle path. See
[SSL and proxies](/configuration/rate-limiting-and-requests#ssl-and-redirects).

## HTTP 429 or repeated transient errors

Fit the request policy to the service quota, for example:

```yaml
rate_limit:
  enabled: true
  requests_per_second: 2
  requests_per_minute: 100
  burst_size: 1
request:
  parallelism: 1
  retry:
    max_retries: 3
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 10
    retry_on_status: [429, 500, 502, 503, 504]
```

Use provider-approved values. Account for other processes/apps using the same
quota; the project's limiter is per process. A Retry-After value can cause
waits longer than `max_delay`. Minute/hour windows and retries can also explain
long pauses without new requests. More concurrency or retries can worsen quota
failures. See [request policy](/configuration/rate-limiting-and-requests).

## Only the first page, repeated pages or no apparent end

Inspect a successful response and two successive requests:

| Observation | Check |
|-------------|-------|
| First page only | Correct parameter for the chosen `iterate_by`; configured page size matches the actual server cap |
| Same IDs on every page | Page/offset field accepted by the API, including nested POST body path |
| Too many pages | Record total versus page count, stale/incorrect count, server ignoring pagination |
| A full-size page ends collection unexpectedly | Configured/fallback page boundary and usable count metadata |
| Configured `data_key` missing | Changed wrapper or an error/login response inside HTTP 200 |

`total_number_key` means records and `pages_number_key` means pages. Setting
one to the other can produce an incorrect boundary. A page shorter than
`page_size_limit` ends collection, so a requested size of 100 with an actual
cap of 50 can stop early. Skip mode computes offsets; native zero-based pages,
cursors and next-link traversal are not automatically supported.

`detect` can suggest selected keys but cannot prove the contract. See
[pagination](/configuration/pagination) and
[backup completeness](/getting-started/data-integrity).

## Estimate fails even though collection is possible

The live estimate requires a usable `data.total_number_key`, a positive page
size and a matching record extraction path. It does not use update filters just
because its mode argument says `update`. APIs with only page-count metadata or
short-page termination can still be backed up after manual contract verification.
Use dry-run for the offline plan and do not invent a record total to satisfy
estimate. See [estimate](/commands/estimate).

## Resume does not continue

| Message/symptom | Action |
|-----------------|--------|
| `No valid checkpoint is available to resume` | Check selected project, checkpoint location/readability and its JSON contents |
| Checkpoint mode mismatch | Use the original full/update mode |
| Checkpoint belongs to another storage path | Recover at the matching location; do not rewrite a path casually |
| Checkpoint storage missing | Restore the referenced archive/staging and its sidecar together |
| `Backup is already complete` | This checkpoint is done; a new collection uses a fresh command without `--resume` |

Use `run full --resume` for a staged full backup and `update --resume` for its
update generation. `run continue` scans published flat page names and does not
recover full staging. Follow recovery instead uses `follow continue`.

Custom relative state/checkpoint paths resolve from the working directory, even
with `-p`. Lifecycle checkpoints are written when the periodic interval is 0.
Keep `.partial` storage and any matching `.journal` sidecar; the journal may hold
saved pages. If downloading finished before interruption, resume may complete
publication and state recovery without more HTTP requests. See [run](/commands/run).

## Pages were saved but the command failed

Missing pages, exhausted requests, extraction failures or unsuccessful storage/
publication keep a run incomplete. `continue_on_error: true` permits later
requests but does not turn gaps into success. The checkpoint advances only
through contiguous saved progress; recover from the first unresolved page with
the matching command.

Successful state/watermark remains unchanged. A previous published full archive
can still be exported, while an incomplete update can already have pages in main
storage. Recover updates before using their export as a verified dataset. Do not
edit state/checkpoint counters to bypass the failure.

## Empty, unexpected or repeated export records

First inspect `info`, then the saved source and extraction paths. Do not replace
an existing backup with a fresh full run merely to diagnose an empty export.

- An existing unnamed `details.zip` with follow configured becomes the export
  source; its `follow_data_key` differs from the main `data_key`.
- A missing/null field never matches a `--where` condition. Numeric-looking
  filter values are converted to numbers, so a string ID may not match.
- `--fields` omits missing/null selected fields; nested paths become literal
  flat output keys.
- Original pages and retained update generations all contribute records;
  `item_key` does not deduplicate repeated IDs.
- `.json` selects JSON Lines, so a whole-file JSON-array parser is inappropriate.

Try an unfiltered export to a **new** filename, then compare representative
records. See [filter grammar](/configuration/export-filters) and
[export verification](/use-cases/export-and-storage).

## Parquet, output path or disk-space failure

Install optional dependencies into the environment running the command:

```bash
python -m pip install 'apibackuper[recommended]'
```

Then check for inconsistent record types/schema if Parquet still fails. JSONL
can be a useful format for inspecting flexible records before normalization.
Create the output parent directory and keep the filename outside source storage.
Filesystem backups reject export anywhere under their own root. Export replaces
existing output only after success, but it needs space for the temporary output.
Full backup publication can also need old and staged storage at the same time.

## Follow or attachment collection is incomplete

| Symptom | Check |
|---------|-------|
| Missing follow ID | Separate `follow_item_key` configured and present on every list record |
| Old detail objects skipped | `follow continue` reuses names; use a deliberate full refresh for existing IDs |
| Missing unnamed details | Named rule archives are not automatic sources for normal export/getfiles |
| Unsupported file source | `getfiles` requires ZIP main storage |
| New attachment links ignored | `allfiles.csv` discovery cache must be refreshed after source updates |
| A different/updated file is skipped | Destination-name collision or existing filename; no content revalidation |
| aria2 command finished but files are absent | Running RPC service, queued transfer status and separate output/policy |

See [follow and files](/use-cases/follow-and-files) before clearing caches or
moving outputs. Preserve the source collection while investigating.

## Prepare a useful diagnostic report

Include the exact command and working directory, Python/package versions,
selected config format, sanitized relevant sections, a small sanitized response
showing the wrapper/pagination and the first causal error. Note whether the
failure was a first full run, recovery, update, follow or export.

Review logs and samples for secrets and private data before sharing. Report
saved-state status separately from the latest command result, and retain the
original recovery files locally. See [community](/development/community) for
project support channels.
