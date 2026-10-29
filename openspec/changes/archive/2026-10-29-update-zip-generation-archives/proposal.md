# Change: Store ZIP update generations in their own archives

## Why
`ZipStorageBackend.close()` (`apibackuper/storage/backends.py`) compacts the
journal by copying every existing member into a new ZIP and replacing the old
one. An `update` that adds one page to a 10 GB `storage.zip` therefore rewrites
10 GB, needs twice the disk space, and gets slower with every generation. For
long-running archives with frequent updates this is the dominant cost.

## What Changes
- With ZIP storage, each update generation is written to its own archive
  `storage.zip.runs/<id>.zip`, with its own `.journal`, instead of into
  `storage.zip`. Compaction touches only that small archive.
- `ZipStorageBackend` presents the base archive and the generation archives as
  one namespace: members keep their names (`runs/<id>/page_N.json`), so export,
  follow, `getfiles`, `info`, fixity manifests and `verify` work unchanged.
- Publishing a full backup also retires the previous backup's generation
  archives, crash-safely, matching today's behaviour where a full backup
  replaces history.
- Archives whose update generations are still inside `storage.zip` remain
  readable; new updates go to separate files, and mixed layouts are supported.
- **BREAKING** for tools that read `storage.zip` directly: new update
  generations are no longer inside it. The documented layout lists
  `storage.zip.runs/*.zip`; `info --stats` reports `generation_archives`.

## Impact
- Affected specs: `storage-backend`, `backup-update`
- Affected code: `apibackuper/storage/backends.py`,
  `apibackuper/storage/session.py`, docs for storage and recovery
- Not affected: SQLite and filesystem backends, which already write in place.
