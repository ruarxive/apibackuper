---
title: "Python API"
description: "Use ProjectBuilder and storage backends from Python with explicit cleanup"
---
# Python API

The current programmatic entry point is
`from apibackuper.cmds.project import ProjectBuilder`. It loads the same project
files as the CLI. Import storage classes from `apibackuper.storage`. The
orchestration helpers in `cmds.backup`, `cmds.runner`, `cmds.fetch` and private
methods are implementation details; prefer the facade methods below.

## Back up and export

Complete the [quick start](/getting-started/quick-start) and keep its local
server running. Run this script from the repository root, where `demo/` exists:

```python doc-test
import json
from pathlib import Path

from apibackuper.cmds.project import ProjectBuilder

project_path = Path("demo").resolve()
project = ProjectBuilder(str(project_path))
try:
    valid, errors, warnings = project.validate_config(verbose=True)
    if not valid:
        raise ValueError(f"Invalid project: {errors} errors, {warnings} warnings")
    project.run("full")
    destination = project_path / "python-items.jsonl"
    project.export("jsonl", str(destination), fields=["id"], where="id >= 3")
    rows = [json.loads(line) for line in destination.read_text().splitlines()]
    assert sorted(row["id"] for row in rows) == [3, 4, 5]
    report = project.info(stats=True)
    assert report["run"]["records_processed"] == 5
finally:
    project.http.close()
```

Construction loads configuration and credentials but does not download API
pages. There is no `ProjectBuilder` context manager. Close its Requests session
in `finally`; run/export workflows manage their own storage handles.

## Facade methods

| Method | Result and behavior |
|--------|---------------------|
| `ProjectBuilder.create(name)` | Static scaffold operation; writes minimal legacy INI |
| `validate_config(verbose=False)` | `(valid, error_count, warning_count)`; can print diagnostics |
| `validation_report(verbose=False)` | `{"valid", "errors", "warnings"}` with `path`, `message` and `hint` per issue; prints nothing |
| `run(mode, resume=False)` | Full or continue/incremental backup; returns `None` |
| `sample(max_pages)` | Collect at most `max_pages` pages into a temporary archive; returns counts, fields and a preview |
| `update(resume=False)` | Retained update generation; returns `None` |
| `follow(mode="full")` | Follow full/continue; returns `None` |
| `getfiles()` | Download associated files from ZIP sources |
| `export(format, filename, fields=None, where=None)` | Write an export; `fields` is a list, not a comma-separated string |
| `info(stats=False)` | Dictionary report; `stats=True` includes storage statistics |
| `detect(write_config=False, probe=True)` | Dictionary of suggestions, record fields and a sample record; contacts the API, and probes pagination with extra requests unless `probe=False` |
| `estimate(mode)` | Print a live estimate and return its figures as a dictionary |

Use `run("full", resume=True)` or `update(resume=True)` to recover. The same
[backup completeness](/getting-started/data-integrity) and history rules apply
as in the CLI. Output filenames resolve from the process working directory;
absolute paths make embedded usage less surprising.

## Errors and logging

The facade raises exceptions instead of converting failures to CLI exit codes.
Handle `ValueError` for invalid settings, filter expressions and unsafe output
paths; `RuntimeError` for failed/incomplete operations; and `OSError` subclasses
for filesystem failures. Unset YAML variables are reported as
`apibackuper.cmds.config_loader.UnresolvedEnvVarError` (a `KeyError` subclass).
Some configuration errors are deferred until validation or execution, so
validate explicitly before starting a job. `getfiles` has legacy early-return
paths for unsupported or missing sources; inspect its output and files.

`ProjectBuilder` adds a file handler for `settings.logfile` (default
`apibackuper.log`, in the process working directory) to the **root logger** and
sets the root level. It replaces only file handlers that apibackuper installed
earlier; your application's handlers stay attached. `logging.level` controls
the threshold; absent that section, the default is DEBUG. Restore the root level
after construction if necessary, or invoke the CLI in a subprocess to isolate
it. Construction can read credential files and open a log file, so keep it
inside your application's resource/error-handling boundary.

## Direct storage access

```python
from apibackuper.storage import ZipStorageBackend

storage = ZipStorageBackend("demo/storage/storage.zip", mode="r")
try:
    for name in storage.list_objects("page"):
        content = storage.get_object(name, "page")  # JSON bytes, or None
finally:
    storage.close()
```

`SqliteStorageBackend` and `FilesystemStorageBackend` expose the same page/object
operations: `save_page`, `save_object`, `list_objects`, `get_object`, `flush` and
`close`. SQLite stores JSON page payloads as BLOBs in `pages`/`objects` tables;
it does not create a relational row per API record. Constructor options differ:
use `build_storage_backend(storage_type, path, mode)` with `mode` equal to
`read`, `full` or `continue` when selecting a backend dynamically.
Direct writes bypass the backup workflow's publication/checkpoint guarantees.

Legacy `FileStorage`, `ZipFileStorage` and `FilesystemStorage` are deprecated.
See the repository README's migration notes for the replacement mapping.
