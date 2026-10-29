## Context
A ZIP file cannot be appended to safely: Python's `ZipFile(mode="a")`
overwrites the central directory with new members and writes a new one on
close, so a crash in between leaves an archive that standard tools cannot open.
The journal (`.journal/*.pending`) was introduced to avoid this, at the price
of rewriting the archive on close.

## Goals / Non-Goals
- Goals: update cost proportional to the update, not the archive; no change to
  member names or reader code; crash safety equal to today's.
- Non-Goals: splitting the base archive of a full backup (`storage.max_file_size`
  stays reserved); deduplicating pages across generations.

## Decisions
- **One archive per generation.** `save_*("runs/<id>/x")` goes to
  `storage.zip.runs/<id>.zip`; other names go to `storage.zip`. The run ID is already
  validated against `[A-Za-z0-9_-]+` (`storage/session.py`).
- **Reading.** `list_objects` merges the base archive, its journal and every
  `storage.zip.runs/*.zip` (with journals). `get_object` routes by name. A name present in
  both a legacy in-archive generation and a generation archive resolves to the
  generation archive.
- **Writing a generation.** The update session opens only `storage.zip.runs/<id>.zip` for
  writing; `close()` compacts that file. `run full` stages `storage.zip.partial`
  as today.
- **Generation directory.** Generation archives live in `<archive>.runs/`
  (`storage.zip.runs/`), tied to the archive file name, so the staging archive
  `storage.zip.partial` of a full run never sees the published generations.
- **Full publication.** After the staged archive replaces `storage.zip`, move
  `storage.zip.runs/` to `storage.zip.runs.previous/`; delete it after the state
  commit. Each step is repeated safely when `--resume` finishes an interrupted
  publication, and old generations are never deleted before the new state is
  committed.
- **Alternatives considered.** Appending in place (rejected: central-directory
  crash window); a single SQLite container (rejected: changes the format users
  rely on); ZIP64 multi-disk spanning (rejected: poor tool support).

## Risks / Trade-offs
- More files in `storage.zip.runs/` → one per update; documented, and `info --stats`
  reports them.
- Readers that open `storage.zip` directly miss new generations → marked
  breaking; the Python API and CLI are unaffected.

## Migration Plan
No conversion. Existing in-archive generations stay where they are. Rollback:
an older version reading a new archive does not see `storage.zip.runs/*.zip` generations,
so rolling back requires keeping the newer version until a fresh full backup.

## Open Questions
- Should a maintenance command fold generation archives back into one file
  (for example before handing an archive to another tool)? Proposed as a follow-up.
