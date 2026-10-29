# Change: Stream file downloads with a size cap and a fixity manifest

## Why
`getfiles` reads every attachment into memory (`response.content` in
`apibackuper/cmds/project.py`) before storing it, so large files can exhaust
memory. The size limit (`FILE_SIZE_DOWNLOAD_LIMIT`, about 270 MB) applies only
in a `be_careful` mode that the CLI does not expose. Downloaded files have no
checksums, so `verify` cannot cover them, although attachments are often the
most valuable part of an archive.

## What Changes
- Downloads are streamed in chunks to a temporary file next to the destination
  storage, hashed with SHA-256 while they arrive, and then moved into ZIP or
  filesystem file storage without being loaded into memory.
- New `files.max_file_size` (bytes; default unlimited). A download that
  declares or reaches a larger size is stopped, recorded in `files_skipped.list`
  with its reason, and the remaining files are downloaded.
- Each stored file is recorded in `files-manifest-sha256.txt` (BagIt form) in
  file storage. `apibackuper verify` checks downloaded files against it and
  reports changed and missing files like pages.
- A failed or interrupted download leaves no partial member; the next
  `getfiles` downloads it again.
- `be_careful` and its hard-coded limit are removed in favour of `max_file_size`.

## Impact
- Affected specs: new `file-downloads` capability
- Affected code: `apibackuper/cmds/project.py` (`getfiles`),
  `apibackuper/storage/backends.py` (store an object from a file path),
  `apibackuper/cmds/fixity.py` (`verify`), schema, files docs
- Not breaking for the CLI. The Python `getfiles(be_careful=...)` argument is
  deprecated and ignored with a warning.
