---
title: "Best practices"
description: "Prepare, operate, recover and retain repeatable backups with explicit source and verification rules"
---
# Best practices

Build a repeatable backup around a small verified project first. Before a long
or recurring run, know what source view you intend to collect, how a failed run
will recover and how the resulting data will be checked. These practices apply
to CLI use and scripts using the same project.

## Define the dataset before tuning performance

Record the endpoint, HTTP method, account/tenant scope, fixed filters, sorting,
response paths and the API's actual full-page size. Prefer a stable source
snapshot/version when offered. Otherwise use a stable unique sort and document
the collection interval so later checks can account for concurrent changes.

Keep those choices fixed during recovery. An endpoint/filter/schema change can
make saved pages incompatible with later requests. Preserve the existing
collection and use a new project or fresh full backup for a changed dataset
definition. See [backup completeness](/getting-started/data-integrity).

Keep YAML and non-secret request/extraction files under version control. Retain
the tested package version with the project so an upgrade and an API contract
change can be diagnosed separately. Validate after every configuration edit:

```bash
apibackuper validate-config --strict
apibackuper run full --dry-run
```

These are offline checks. They do not authenticate or test live response fields.
Use `estimate full` when the service exposes a usable total count, then inspect
a first completed export rather than treating the estimate as a completeness test.

## Give credentials and paths predictable scope

Keep secret values outside committed YAML/JSON. A file-backed example is:

```yaml
auth:
  type: bearer
  token_file: /run/secrets/catalog_token
```

The file must contain a current non-empty token without a `Bearer ` prefix.
Inline values override credential files; remove an old inline token when
switching sources. Files are read at project load, so a replacement requires
a new CLI invocation. Environment placeholders are another option, but `.env`
is not loaded automatically. See [authentication](/configuration/auth).

Use a fixed working directory and explicit project path for unattended commands.
`-p` does not change the process working directory. Relative credential files,
custom state/checkpoint overrides, logs and exports can resolve outside the
project. Leave default project-local state paths in place, or use absolute
custom paths that are unique to the job.

Follow and built-in attachment requests use project authentication too. Verify
that linked hosts are allowed recipients of those credentials. Keep TLS
verification enabled and resolve certificate/proxy configuration problems before
starting the collection. Shared logs redact recognized secrets, but review
custom headers, hook output and API messages before sharing diagnostics.

## Bound requests and increase concurrency deliberately

A starting policy for a service that permits these limits is:

```yaml
project:
  default_delay: 0
rate_limit:
  enabled: true
  requests_per_second: 2
  requests_per_minute: 100
  burst_size: 1
request:
  parallelism: 1
  connect_timeout: 10
  read_timeout: 60
  verify_ssl: true
  retry:
    max_retries: 3
    backoff_strategy: exponential
    initial_delay: 1
    max_delay: 10
    retry_on_status: [429, 500, 502, 503, 504]
error_handling:
  continue_on_error: false
```

Adapt quotas to the provider and other account consumers. The limiter coordinates
ordinary attempts inside one process; other jobs/applications and aria2 do not
share it. Redirects and OAuth refresh/replay can add exchanges within an attempt.
`default_delay` alone is not an account-wide quota with several workers.

Raise `parallelism` only after observing latency, 429s, stable pagination and
verification results. Parallelism changes collection speed, not source snapshot
consistency. Set active `connect_timeout`/`read_timeout`; the legacy `timeout`
field does not replace that pair. Read timeout is not a total-job deadline.

Retries can replay POST requests as well. Use read/search endpoints where replay
is acceptable. `continue_on_error: true` may collect later pages but still leaves
an incomplete, unsuccessful backup. See
[request policy](/configuration/rate-limiting-and-requests).

## Preserve recovery data and use one writer

For periodic checkpoint saves, merge into your settings:

```yaml
settings:
  checkpoint_interval_pages: 5
```

Lifecycle checkpoints are still written when the interval is 0. Keep the project
config, successful state, checkpoint, working `.partial` storage and corresponding
ZIP `.journal` sidecar together until recovery finishes. A journal can contain
saved data not yet compacted into the ZIP.

| Interrupted operation | Recovery command |
|-----------------------|------------------|
| Main full backup | `apibackuper run full --resume` |
| Change update | `apibackuper update --resume` |
| Detail collection | `apibackuper follow continue` |
| Built-in attachment download | `apibackuper getfiles` again, skipping saved filenames |

A fresh full command starts a new staging collection. It is not a replacement
for recovering unfinished work whose progress you want to retain. Keep the same
mode/storage path and API contract while resuming. Completed checkpoints report
that collection is already complete.

Prevent overlapping writers to a project, its storage and its state files.
For scheduled jobs, use the scheduler's exclusion/locking mechanism and do not
launch an update while its previous run still needs recovery. The tool does not
supply distributed locking or coordinate quotas across processes.

## Verify results at the correct stage

Check the command's exit status before inspecting successful state or exporting.
`info` can still show an earlier successful run after a later failure. A failed
full backup leaves the previous published archive; update pages are appended as
they arrive, so export can include an unfinished update generation. Recover the
update before delivering its output.

For each completed collection, compare:

- Exported row count against the intended source total/scope.
- Distinct IDs and duplicate counts against the expected history model.
- First/last IDs, date boundaries and representative nested values.
- Current totals and schema against a prior verified collection.

`data.item_key` documents identity and does not deduplicate or automatically
configure follow. Set `follow.follow_item_key` separately. Updates need an
API-supported change parameter; a field that looks like a date may represent
creation or business status rather than every modification.

Keep repeated versions when history is required. For a current-object dataset,
select versions downstream using a meaningful revision/timestamp and tie policy.
Interpret deletion events only according to the provider's contract. See
[incremental and update](/use-cases/incremental-and-update).

## Operate detail and file stages explicitly

Refresh details after updating the list when current detail contents matter.
`follow continue` skips saved detail names; use a deliberate full detail refresh
for existing IDs. An old unnamed `details.zip` can remain selected by export
after a main backup changes.

After new references appear, refresh the attachment discovery cache and retain
existing downloads. Existing filenames are skipped even when their remote bytes
change, and URL-path naming can collide across hosts/query strings. Verify file
counts, representative contents and checksums rather than only URL inventories.
See [follow and files](/use-cases/follow-and-files).

## Retain a verifiable collection, then rotate

Stop writers before taking a collection copy. Keep configuration, non-secret
request files, extraction scripts, successful state and storage together. Record
checksums after successful completion and keep a separate retained copy according
to the value of the dataset. A checksum detects byte changes; it cannot prove
source completeness.

Full publication can temporarily require the old archive, new staging and ZIP
journal data at once. Export also creates a temporary output. Budget space for
that overlap, retained update generations and attachments rather than only the
final compressed ZIP.

There is no automatic pruning or restore-to-API operation. For rotation, preserve
the old collection, create and verify a fresh full snapshot, then retire/move
old data according to your policy. Do not edit archive members or checkpoint
values to manufacture a smaller successful history. See
[storage](/configuration/storage) and
[verification examples](/getting-started/data-integrity).
