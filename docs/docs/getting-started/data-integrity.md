---
title: "Backup completeness"
description: "Define a complete source view, verify pagination and exported IDs, understand update history and retain checksummed collections"
---
# Backup completeness

A successful run means the pages required by the configured collection rules
were saved and the operation completed. Completeness also depends on the API's
scope, pagination contract and consistency during collection. Verify those
properties separately from whether an archive opens or a command exits zero.

For a new project, define an expected count, identifier, collection boundary and
verification sample before a large run. The
[Quick Start](/getting-started/quick-start) provides a fixed five-record dataset
for practicing these checks.

## Distinguish the guarantees

| Property | Evidence | What still needs checking |
|----------|----------|---------------------------|
| Configuration is valid | `validate-config --strict` succeeds | Live endpoint, permissions and response contract |
| The operation completed | Latest command exits zero, matching successful state | Correct source scope and stopping conditions |
| Saved files are readable | ZIP/JSON parsing, export succeeds | Missing/repeated source records |
| Bytes are retained unchanged | Checksums compared with a trusted saved manifest | Whether the original collection was complete |
| Records match the intended dataset | Source counts, distinct IDs, boundaries and samples reconcile | Source snapshot/late-change semantics |

`info` reports saved successful state. After a later failure it can still report
the preceding run's success. Always use the latest command result as well.

## Understand how collection stops

| Available information | Boundary |
|-----------------------|----------|
| Usable `total_number_key` record count | `ceil(total / page_size_limit)` pages |
| No usable record total, but usable `pages_number_key` | Reported page count |
| Neither usable count | Fallback boundary of at most 20,000 pages |
| Extracted page shorter than configured size | Stop early, including an empty terminating page |
| Bare single-object response | Save the object and stop |

Configure the service's **actual returned full-page size**, not only the requested
maximum. If it caps a request for 100 records at 50, a configured size of 100 can
make the first response look like the end. A low/incorrect total can also truncate
a collection that exits successfully. Reaching the fallback boundary is not
proof there are no later objects.

For the local fixture, the total is 5 and page size is 2. Pages contain IDs
`[1,2]`, `[3,4]`, `[5]`, so three saved pages and five rows are expected. For six
records with no usable count and size 2, finding the end requires a fourth,
empty request; an empty terminating page is not stored as a record page.

`start_page` defaults to 1 and must be positive. Page numbers are positive;
skip mode computes `(page - 1) * page_size_limit`. Native zero-based pages,
cursors and next links are not automatic continuation mechanisms. Range mode
has its own from/to boundaries; see [pagination](/configuration/pagination).

Parallel requests may already be in flight at an end page. The ordered collector
consumes pages at that boundary, and missing pages/exhausted retries make the
run unsuccessful. Parallelism does not strengthen the API contract.

## Fix the source view across pages and recovery

Prefer an API snapshot token, fixed export version or bounded query interval if
the service provides one. Otherwise use the API's stable ordering by a unique,
immutable key and document collection start/end times. Put supported fixed
filters/sorting in `params.json` and keep them constant across requests.

Consider a page boundary after IDs 1 and 2. If a new earlier object is inserted
before the next offset request, page 2 can repeat ID 2; if an earlier object is
deleted, another ID can be skipped. Stable sorting helps identify this problem
but does not create a snapshot while the source changes.

Authentication/tenant scope is part of the dataset definition. A valid token
can return only a permitted subset with a perfectly plausible total. Confirm
what the account should see, and compare against a count for the same filters,
scope and time boundary.

During resume, keep endpoint, account scope, fixed parameters, page size,
extraction paths/code and source version unchanged. A changed definition needs
a fresh verified collection, not a mixture of old and new page semantics.

## Verify an exported baseline

After a completed fresh full backup, export before the first follow if you need
to check list records:

```bash doc-test
apibackuper info --json
apibackuper export items.jsonl
```

For the local fixture, save the following as `verify_records.py` and run it in
the project directory. For a real API, replace `expected_count`, identifier and
required fields with independently established expectations:

```python doc-test
import json
from collections import Counter
from pathlib import Path

expected_count = 5
required_fields = {"id", "title", "updated_at"}
ids = Counter()
rows = 0
with Path("items.jsonl").open(encoding="utf8") as stream:
    for number, line in enumerate(stream, 1):
        record = json.loads(line)
        if not isinstance(record, dict) or not required_fields.issubset(record):
            raise ValueError(f"Unexpected record shape on line {number}")
        key = record["id"]
        if not isinstance(key, (str, int)) or isinstance(key, bool):
            raise ValueError(f"Expected a scalar identifier on line {number}")
        ids[key] += 1
        rows += 1
assert rows == expected_count, (rows, expected_count)
assert len(ids) == expected_count, "Duplicate IDs in this fresh baseline"
print("Verified rows:", rows, "distinct IDs:", len(ids))
```

The input is read one line at a time, but the identifier counter uses memory
proportional to distinct IDs. Use an external/database comparison for very large
collections. An equal count alone can hide one missing and one repeated object;
check identifiers and representative content too.

For production verification, compare first/last IDs, date boundaries, nested
fields and a small independent source sample. Track counts/schema across runs
to detect unexpected drops. Do not apply the baseline uniqueness assertion to
update history where repeated versions are intentional.

## Interpret updates, boundaries and deletions

`update` sends the last successful bound through a configured API parameter.
For change-key mode, the bound is the maximum observed record change value;
for timestamp mode, it is the prior successful run's start timestamp in UTC ISO
form, with a legacy fallback to `last_run_end`.

The provider defines inclusive/exclusive boundaries, timestamp precision and
late visibility. Equal timestamps can repeat records at the boundary. Backdated
edits or records that become visible late can be missed by a simple greater-than
filter; use provider-supported overlap/reconciliation or periodic full snapshots.
A business/creation date may not represent all modifications.

Each update retains a generation alongside earlier pages. Export includes all
retained records and does not infer a latest version from order or `item_key`.
Select a current view downstream using a meaningful revision/timestamp and an
explicit conflict policy. See
[version-selection recipe](/use-cases/export-and-storage#5-build-a-current-object-view-from-history).

Objects disappearing from the API are not removed from history. Only interpret
a deletion when the provider supplies an event/tombstone or when a verified full
snapshot supports that comparison. An absent object in a partial or scoped
collection is not evidence of deletion.

Failed updates preserve the successful watermark but can already have appended
pages to main storage. Recover them before exporting a verified history. A fresh
update after failure can repeat records in another generation; `update --resume`
continues the original one. See [updates](/use-cases/incremental-and-update).

## Verify details and attachment bytes separately

Follow requests happen after the list collection, so details may describe a
later source state. Compare distinct list IDs with returned detail IDs. An old
unnamed details archive can stay selected by export after a new main backup;
refresh it deliberately rather than assuming `run` did so.

Attachment discovery caches references, and file download skips existing names.
Check expected unique paths, non-empty content, representative file formats and
checksums. A URL inventory or HTTP 200 can still correspond to an expired signed
link or an HTML error page. Clearing discovery does not revalidate bytes at a
saved filename. See [follow and files](/use-cases/follow-and-files).

## Record byte-level evidence after completion

Stop writers before recording checksums or copying a collection. For a completed
local ZIP project, this script writes a small manifest:

```python doc-test
import hashlib
import json
from pathlib import Path

names = [
    "apibackuper.yaml",
    "apibackuper_state.json",
    "apibackuper_checkpoint.json",
    "storage/storage.zip",
]
checksums = {}
for name in names:
    digest = hashlib.sha256()
    with Path(name).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    checksums[name] = digest.hexdigest()
Path("checksums.json").write_text(json.dumps(checksums, indent=2) + "\n", encoding="utf8")
print("Recorded SHA-256 for", len(checksums), "files")
```

Include relevant non-secret request files and extraction scripts in your own
manifest; adapt paths for other backends/details/files. Retain the manifest
separately with the collection. On later verification, compute the same hashes
and compare to that retained manifest rather than overwriting it. Checksums
establish byte identity with the retained copy, not semantic completeness or
authenticity of the API response.

## Retain enough to reproduce and recover

Keep the archive, configuration, non-secret request files, extraction code,
successful state, tested package version and verification evidence together.
A stopped but unfinished collection also needs its checkpoint, referenced
`.partial` storage and matching `.journal` directory; journals can contain pages
not yet compacted into ZIP. See [recovery](/commands/run).

Create an independent retained copy according to your collection's needs. Full
runs replace published main storage after success; updates grow history, and
there is no automatic pruning or restore-to-API command. For rotation, preserve
the old collection, create a fresh full snapshot and verify it before retiring
old data. Do not run overlapping writers or edit checkpoint/archive members to
make an incomplete collection appear complete.
