---
title: "verify"
description: "apibackuper verify command reference"
---
# `verify`

Checks the saved pages against the fixity manifests written by successful runs.
Verification reads local storage only; it does not contact the API.

```bash
apibackuper verify
apibackuper verify -p budgettofk
apibackuper verify --strict
apibackuper verify --json
```

## Manifests

Every successful `run` or `update` writes two members into the generation it
publishes. The base pages use the archive root; each update uses `runs/<id>/`.

| Member | Content |
|--------|---------|
| `manifest-sha256.txt` | `<sha256>  <member>` per page, sorted by member name (the BagIt manifest form) |
| `run.json` | apibackuper version, run ID, mode, start and end time (UTC), page and record counts, the API total when known, and `config_sha256` |

`config_sha256` hashes the resolved configuration with credential values
redacted, so rotating a token does not change it, while any other setting does.
`run continue` rewrites the base manifest to cover every base page. Neither
member starts with `page_`, so export, follow, `info` and resume ignore them.

## Result and exit status

For each generation, `verify` reports the number of verified pages and lists:

- `changed`: a listed member whose bytes no longer match its digest;
- `missing`: a listed member that is no longer stored;
- `unlisted`: a page that the manifest does not list.

The command exits `1` when any listed member is changed or missing. Unlisted
pages and generations without a manifest, such as archives written by earlier
versions, are reported but pass. With `--strict` they fail as well. `--json`
prints the whole report, including `ok`, `strict` and `checked_at`.

The time and result of the last verification are stored in the state file and
shown by [`info`](/commands/info). A later successful run replaces the state and
clears this record, because the new data has not been verified yet.

Verification establishes that the stored bytes are the ones the run saved. It
does not prove that the API returned complete data; see
[backup completeness](/getting-started/data-integrity).
