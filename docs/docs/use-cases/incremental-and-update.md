---
title: "Incremental and update"
description: "Choose the right recovery command, configure server-side change filters and verify retained history"
---
# Incremental and update

There are two different jobs: recovering pages from an interrupted collection,
and asking an API for records changed since a successful collection. Choose the
command from the state of your project, then verify what the API returned.

## Choose the operation

| Situation | Command | Effect |
|-----------|---------|--------|
| Interrupted full backup in `.partial` storage | `apibackuper run full --resume` | Reuse its checkpoint and finish that full backup |
| Published archive with a missing/unfinished page sequence | `apibackuper run continue` | Start at the first missing flat page |
| Same operation using the legacy alias | `apibackuper run incremental` | Same behavior as `run continue` |
| New changes after a successful baseline | `apibackuper update` | Send the saved watermark when configured; retain a new generation |
| Interrupted update | `apibackuper update --resume` | Reuse the interrupted update generation and checkpoint |
| New complete replacement snapshot | `apibackuper run full` | Publish a new full archive after successful collection |

`continue` checks page names, not record IDs or modification dates. It does not
refresh already saved pages. Use the matching `--resume` command for recovery
of a checkpointed run; a completed checkpoint reports that it is already done.

## 1. Establish the API's change contract

The configuration below assumes an illustrative API at `api.example.com` that:

- Returns `{"total":N,"items":[...]}` with 100 records on a full page.
- Uses one-based `page` and `per_page` parameters.
- Accepts `modified_since` to filter by the record's `metadata_modified` value.
- Returns the total for that filtered result, with stable ordering.

Replace these names and the URL with your service's actual contract. Verify
whether the lower bound is inclusive, which timestamp format is accepted, and
how equal timestamps, late changes and deleted records are represented. The
local quick-start server does not implement change filtering.

## 2. Configure a baseline and change-key updates

In a dedicated project directory, save `apibackuper.yaml`:

```yaml config
settings:
  name: changing-catalog
  checkpoint_interval_pages: 5
project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page
  update_mode: by_change_key
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
  change_key_param: modified_since
data:
  data_key: items
  total_number_key: total
  item_key: id
  change_key: metadata_modified
storage:
  storage_type: zip
```

Put API-supported fixed filters and sorting in `params.json`. Keep them stable
across baseline and update runs. Do not hard-code a competing `modified_since`
value there when the saved state is intended to control that bound.

Run the baseline first:

```bash
apibackuper validate-config --strict
apibackuper run full --dry-run
apibackuper estimate full
apibackuper run full
apibackuper info --json
apibackuper export baseline.jsonl
```

The successful state records the maximum observed `metadata_modified` value as
`last_change_key`. On the next update, that value is passed as `modified_since`.
The `data.change_key` path starts at each extracted record, while
`data.data_key` starts at the response root.

Change values must be comparable and ordered in the way the API expects.
Consistently normalized ISO timestamps can be compared as strings; mixed time
zones, formats or value types need normalization. A creation date or business
status date may miss later edits and is not automatically a suitable change key.

## 3. Collect a new generation

After the upstream dataset has changed:

```bash
apibackuper update --dry-run
apibackuper update
apibackuper info --json
apibackuper export history.jsonl
```

Dry-run previews the local plan and does not prove the API honors the filter.
On the first real update, inspect the returned records and the request contract:
an ignored filter can produce another full collection.

For a baseline containing IDs 1 and 2, followed by an update returning a changed
ID 2 and a new ID 3, export contains **four historical records**, with ID 2 twice.
The ZIP layout is conceptually:

```text
page_1.json
runs/<first-update-id>/page_1.json
runs/<later-update-id>/page_1.json
```

Each new update retains its own pages. `item_key: id` does not turn updates into
an upsert, and export does not choose the newest version. Use the deterministic
version-selection recipe in [export and storage](/use-cases/export-and-storage).

## Timestamp-based APIs

If the API accepts a collection-time lower bound rather than a record-derived
change key, replace the corresponding project and parameter settings with:

```yaml
project:
  url: https://api.example.com/items
  http_mode: GET
  iterate_by: page
  update_mode: by_timestamp
params:
  page_number_param: page
  page_size_param: per_page
  page_size_limit: 100
  update_since_param: changed_after
```

Keep the remaining required sections from the full configuration. In this mode,
the next update sends the previous successful run's `update_watermark`: the UTC
ISO timestamp captured at its **start**. Legacy state without this field falls
back to `last_run_end`. The start watermark allows the next collection to cover
changes made while the previous run was downloading, so overlap is expected.

Confirm that the API accepts that exact timestamp representation and defines a
compatible boundary. Backdated edits and delayed visibility can still require
periodic full reconciliation. Without an explicit mode, a configured
`data.change_key` selects `by_change_key`; otherwise the default is
`by_timestamp`. Choose the mode explicitly for an operational project.

A missing successful watermark or missing request parameter means no saved
lower-bound filter can be injected. An update may then request the complete
collection. `custom_script` is reserved and execution rejects it.

## Recover without advancing successful state

If a run fails, resolve the HTTP/storage problem, keep its data and checkpoint,
then use the command matching the interrupted operation:

```bash
# Recover an interrupted full backup.
apibackuper run full --resume
```

```bash
# Recover an interrupted update instead.
apibackuper update --resume
```

For ZIP storage, keep the archive or `.partial` path together with its `.journal`
sidecar. The checkpoint tracks the contiguous durably saved prefix; recovery
starts at the first unresolved page and can safely replay a page. A pending
publication step can also be completed from saved data.

Failed/incomplete runs return a nonzero exit and leave the previous successful
watermark unchanged. `info` can therefore still show `success` from that earlier
run. `update --resume` keeps the same generation; a fresh `update` starts another
one and can repeat records collected before the failure. Avoid changing the
endpoint, authentication scope, filters, pagination or storage path mid-recovery.

Update pages are appended to main storage during collection. An export made
before an interrupted update is recovered can include its incomplete generation;
wait for successful recovery before treating that export as a verified result.

## Verify recurring collection

Before relying on updates, exercise one known upstream edit and one new object.
Confirm that both appear, that the stored watermark advances only after success,
and that a second update behaves according to the API's boundary semantics.
Compare history row counts separately from distinct object counts.

Deletion is API-specific. If deleted objects disappear from the list without a
tombstone event, update cannot infer their removal. If deletion events are
returned, retain and interpret them downstream. Periodic full snapshots can
help reconcile changes missed by the incremental contract.

Run at most one writer per project/storage path. An external scheduler should
check exit status, recover unfinished work before starting another update, and
provision credentials for that invocation. Updates grow retained history;
there is no automatic pruning. Preserve the old archive, state and configuration
before rotating to a verified fresh full snapshot.

| Symptom | Likely cause |
|---------|--------------|
| Every update downloads the whole dataset | Missing watermark/parameter, or API ignores the supplied filter |
| Recently edited objects never appear | Field represents creation/business date rather than all modifications |
| IDs appear repeatedly in export | Retained versions and inclusive boundaries; expected history behavior |
| `continue` does not fetch changed records | It fills missing page names rather than querying changes |
| Resume rejects the checkpoint | Wrong mode/project/path, missing checkpoint, or a completed run |

See [backup completeness](/getting-started/data-integrity) for source consistency
limits and [run](/commands/run) for checkpoint details.
