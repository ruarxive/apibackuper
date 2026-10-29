## 1. Backend
- [x] 1.1 Route `runs/<id>/` names to `storage.zip.runs/<id>.zip` in `ZipStorageBackend`,
      each with its own journal and compaction
- [x] 1.2 Merge base, legacy in-archive and per-generation members in
      `list_objects`/`get_object`, preferring generation archives
- [x] 1.3 Open only the generation archive for writing during `update`

## 2. Publication
- [x] 2.1 Retire `storage.zip.runs/` through `storage.zip.runs.previous/` when a full backup
      is published, with recovery after interruption

## 3. Tests and docs
- [x] 3.1 Tests: update does not rewrite `storage.zip` (mtime/size unchanged),
      export/verify/follow read all generations, legacy mixed layout, full
      publication retires old generations, interrupted publication recovery
- [x] 3.2 Update the storage layout and recovery docs and `CHANGELOG.md`
