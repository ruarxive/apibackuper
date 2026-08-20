---
title: "Incremental and update"
description: "Add new records or refresh changed ones without a full re-download"
---
# Incremental and update

`project.work_modes` is a comma-separated list of `full`, `incremental`, and
`update`. Full mode always walks every page. The other two reuse stored state.

## Incremental

Incremental mode adds records that are not already in storage. You need a
stable unique key:

```yaml
data:
  item_key: id
```

Composite keys are comma-separated: `item_key: year,code`.

## Update

Update mode re-fetches records whose change field moved. Configure both an
item key and a change key:

```yaml
settings:
  state_file: apibackuper_state.json
  checkpoint_file: apibackuper_checkpoint.json
  checkpoint_interval_pages: 5

project:
  work_modes: full,incremental,update
  update_mode: by_change_key

data:
  item_key: id
  change_key: metadata_modified
```

```bash
apibackuper update
apibackuper update --resume
```

`update_mode` can be `by_change_key` (default), `by_timestamp`, or
`custom_script`.

## Resume a long run

```bash
apibackuper run full --resume
```

Checkpoints are written every `settings.checkpoint_interval_pages` pages.

Feature example: `examples/features/update-resume/`.
