---
title: "Files"
description: "Extract attachment URLs or IDs, choose filenames and output storage, refresh caches and configure aria2"
---
# Files

`getfiles` extracts attachment references from saved records and downloads the
referenced bytes. Configure it after you have verified the list or detail
backup; it is a separate command, not an automatic step in `run`.

## Source selection and requirements

The main backend must be ZIP (`storage.storage_type: zip`). Downloaded-file
output can independently be ZIP or filesystem storage. The source is:

| Project configuration | Where references are read |
|-----------------------|---------------------------|
| No `follow` section | Published `storage.zip`, using `data.data_key` |
| A `follow` section exists | Unnamed `details.zip`, using top-level `follow_data_key` |

Named detail archives are not selected automatically. Complete the corresponding
`run`/`follow` before invoking `getfiles`. A configured follow section with no
unnamed detail archive does not fall back to the list pages. Use a separate
project/configuration without follow when the attachments should come from the
list rather than details.

## Download complete URLs

For a record such as:

```json
{"id": 42, "document_url": "https://files.example.com/reports/42.pdf"}
```

use:

```yaml
files:
  fetch_mode: prefix
  root_url: ""
  keys: document_url
  storage_mode: filepath
  file_storage_type: zip
  use_aria2: false
```

An empty prefix leaves the extracted URL unchanged. `storage_mode: filepath`
uses its URL path for the saved filename, so this file is stored as
`reports/42.pdf` inside `storage/files.zip` after filename sanitization.

```bash
apibackuper run full
apibackuper getfiles
```

When references are in detail objects, insert `apibackuper follow full` before
`getfiles` and configure the matching detail extraction key.

## Build URLs from relative paths

For `{"attachment":"reports/42.pdf"}`:

```yaml
files:
  fetch_mode: prefix
  root_url: https://files.example.com/
  keys: attachment
  storage_mode: filepath
  file_storage_type: filesystem
```

This concatenates the strings into
`https://files.example.com/reports/42.pdf`. The prefix must contain any needed
slash. It is not general URL resolution: `root_url` ending in `/` plus a value
starting in `/` produces a double slash.

## Build URLs from document IDs

For `{"document_id":42}` and an endpoint `/documents/42`:

```yaml
files:
  fetch_mode: pattern
  root_url: "https://files.example.com/documents/{}"
  keys: document_id
  storage_mode: id
  default_ext: pdf
  file_storage_type: filesystem
```

`pattern` substitutes the extracted scalar into `{}` using Python string
formatting. The example downloads `/documents/42` and stores `42.pdf` under
`storage/files/`. Choose a default extension only when the API's content type
is known; it does not convert the bytes to that format.

## Field reference

| Field | Requirement / default | Meaning |
|-------|-----------------------|---------|
| `fetch_mode` | Required `prefix` or `pattern` | URL concatenation or `{}` substitution |
| `root_url` | Required string | Literal prefix, empty prefix for complete URLs, or format pattern |
| `keys` | Required comma-separated string | Record paths containing attachment references |
| `storage_mode` | `filepath` | Use URL path; `id` uses the extracted value instead |
| `default_ext` | Omitted | Extension appended to ID-mode filenames |
| `file_storage_type` | `zip` | `zip` or `filesystem`, independent of main ZIP source |
| `use_aria2` | false | Use a running external aria2 RPC service instead of the built-in downloader |

Use keys without spaces around commas, such as `document_url,attachments.url`.
Record paths use `settings.splitter`. Values should be scalar strings/numbers
or simple lists of references, not arbitrary objects. For example:

```json
{"attachments": [{"url": "https://files.example.com/a.pdf"}, {"url": "https://files.example.com/b.pdf"}]}
```

can be discovered using `keys: attachments.url`. Discovered references are
collected into a set, so an identical URL/ID is downloaded only once per cache.
This is independent of `data.item_key` and record identity.

## Filenames and collisions

`filepath` ignores the hostname and query string when choosing the name. URLs
`https://a.example/report.pdf` and `https://b.example/report.pdf`, or two signed
URLs differing only in their query, can map to the same destination filename.
An already saved filename is skipped; it is not compared with remote content.
A download answered with HTTP 404 or 410, or matching a `missing` response rule,
is recorded in `files_skipped.list` with its status as the reason, and the remaining files are downloaded; the
next `getfiles` run tries it again. Other failures stop the command.
Choose references and storage mode that give unique names for your dataset.

`id` uses the extracted value, optionally followed by `default_ext`. It does not
infer a separate ID from a URL. Filename sanitization prevents unsafe path
segments, but does not provide versioning or a content-addressed archive.
In ordinary CLI use, `filepath` derives the name from the URL rather than
`Content-Disposition`.

## Download inventory and discovery cache

With default storage paths, `getfiles` can create:

```text
storage/
  allfiles.csv         # cached discovered values, one per line
  files.zip            # downloaded objects when output is ZIP
  files/               # downloaded objects when output is filesystem
  files.list           # URLs recorded by the built-in downloader
  files_skipped.list   # skipped files, including HTTP 404/410 responses
```

Only the selected output backend receives the built-in file payloads. Despite
its extension, `allfiles.csv` is a line-oriented reference cache, not a table
with record metadata. Later runs read it instead of rescanning source records.

After a new backup/update/follow adds references, remove **only the discovery
cache** to rescan while retaining existing downloads. For example, in Python:

```python
from pathlib import Path

Path("storage/allfiles.csv").unlink(missing_ok=True)
```

Run `getfiles` again. Existing filenames are still skipped. To refresh changed
bytes at an existing name, preserve the old file/archive and use a deliberate
fresh file-output collection; deleting the discovery cache alone is insufficient.
There is no CLI flag for conditional HTTP revalidation or download versioning.

## HTTP policy and large files

The built-in downloader uses the project's authentication, `headers.json`, SSL
verification, connection/read timeouts, retries and rate limits. `params.json`
is not applied as an attachment request body. Follow/file URLs may point at
another host; use endpoints allowed to receive the project authentication.

The built-in path reads a response into memory before storing it. It does not
provide automatic large-file splitting, a CLI size-cap option or streaming
resume of partial attachment bytes. Main page checkpoints do not track partial
file transfers; the repeated command skips fully saved filenames.

## aria2 integration

Install `aria2p` (or the `recommended` extra), start an aria2 RPC service and
configure `use_aria2: true`. The integration connects to:

```text
http://localhost:6800
RPC secret: empty
Output directory: <storage directory>/files/
```

The client queues URLs and lets aria2 perform the transfers; command completion
does not certify that the queued downloads have completed. The ordinary ZIP file
backend is not populated with those external transfer results. Installing the
Python package alone does not start aria2. RPC host, port and secret are not
configurable through the current project schema.

Project auth headers, retry limits, SSL settings and rate limits are not passed
to aria2 as a download policy. Configure the service separately and prefer the
built-in downloader when the project depends on those settings.

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Unsupported main storage | `getfiles` requires ZIP main storage even with filesystem file output |
| Missing `details.zip` | A follow section selects unnamed details; named rules are not automatic sources |
| No newly linked files found | Remove the stale discovery cache after finishing the updated source backup |
| URL contains duplicated/missing slash | Prefix concatenation is literal; inspect `root_url` and extracted values |
| A different document is skipped | Filename collision or a saved filename whose remote bytes changed |
| aria2 queues fail or never finish | RPC service, local endpoint, empty secret and independent download credentials/policy |
