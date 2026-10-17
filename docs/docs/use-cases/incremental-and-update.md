---
title: "Incremental and update"
description: "Resume saved pages and retain new or changed records"
---
# Incremental and update

`run continue` (also `run incremental`) resumes from the first missing page in
the existing archive. It does not deduplicate records by `item_key`.

`update` requests records after the last successful state watermark and retains
them as a new generation. Earlier generations remain available. Export emits
historical records from every retained generation, including repeated object IDs.

```yaml
settings:
  name: incremental-example
  checkpoint_interval_pages: 5
project:
  url: https://api.example.com/items
  http_mode: GET
  update_mode: by_change_key
params:
  page_size_limit: 100
  page_number_param: page
  change_key_param: modified_since
data:
  data_key: items
  total_number_key: total
  change_key: metadata_modified
storage:
  storage_type: zip
```

```bash
apibackuper update
apibackuper update --resume
apibackuper run full --resume
```

Use the actual parameter name accepted by your API for `change_key_param`.
For timestamp updates, set `update_mode: by_timestamp` and
`params.update_since_param`. The timestamp watermark is captured at the start
of the last successful run, preventing changes made during collection from
falling into a gap. Legacy state files fall back to `last_run_end`.

The default mode is `by_change_key` when `data.change_key` is configured,
otherwise `by_timestamp`. `custom_script` is reserved and execution rejects it
explicitly.

Failed or partial runs return a nonzero exit code and retain the previous
successful state. Resume reuses the interrupted generation and retries the
first unsaved page. Keep checkpoint files, `.partial` storage and ZIP `.journal`
directories together until recovery completes. See [run](/commands/run).
