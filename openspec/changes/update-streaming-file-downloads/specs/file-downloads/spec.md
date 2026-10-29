## ADDED Requirements
### Requirement: Streamed downloads
`getfiles` SHALL stream each file to a temporary file in fixed-size chunks and
store it from that file, so memory use does not grow with file size.

#### Scenario: Large attachment
- **WHEN** a 2 GB file is downloaded
- **THEN** it is stored without reading the whole body into memory

### Requirement: File size cap
With `files.max_file_size` set, a file whose declared `Content-Length` or
streamed size exceeds it SHALL NOT be stored. It SHALL be recorded in
`files_skipped.list` with the reason, and the remaining files SHALL be downloaded.

#### Scenario: Undeclared oversize file
- **WHEN** a response without `Content-Length` streams past `max_file_size`
- **THEN** the download stops, no member is stored and the skip is recorded

### Requirement: File fixity manifest
Every stored file SHALL be recorded with its SHA-256 in
`files-manifest-sha256.txt`, and `apibackuper verify` SHALL report stored files
that changed or are missing relative to that manifest.

#### Scenario: Tampered attachment
- **WHEN** a downloaded file is modified after `getfiles`
- **THEN** `verify` reports it as changed and exits with status 1

### Requirement: No partial files
A download that fails or is interrupted SHALL leave no stored member and no
manifest entry, so the next `getfiles` run downloads it again.

#### Scenario: Connection drops mid-download
- **WHEN** the connection fails after half of a file was received
- **THEN** the file is absent from storage and from the manifest
