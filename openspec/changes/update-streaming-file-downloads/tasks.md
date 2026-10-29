## 1. Storage
- [x] 1.1 Add `save_object_from_path(name, path)` to the ZIP (journal move) and
      filesystem (atomic rename) backends

## 2. Downloads
- [x] 2.1 Stream responses (`stream=True`) in chunks to a temporary file,
      hashing with SHA-256
- [x] 2.2 Enforce `files.max_file_size` from `Content-Length` and while
      streaming; record skips in `files_skipped.list`
- [x] 2.3 Remove temporary files on failure or interruption
- [x] 2.4 Deprecate `be_careful` and drop `FILE_SIZE_DOWNLOAD_LIMIT`

## 3. Fixity
- [x] 3.1 Append each stored file to `files-manifest-sha256.txt`
- [x] 3.2 Make `verify` check file storage against that manifest

## 4. Tests and docs
- [x] 4.1 Tests: large streamed file stays out of memory (chunked mock),
      declared and undeclared oversize files skipped, interrupted download
      leaves no member, manifest written and verified, tampered file detected
- [x] 4.2 Update the files guide, configuration reference and `CHANGELOG.md`
