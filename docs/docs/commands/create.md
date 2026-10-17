---
title: "create"
description: "apibackuper create command reference"
---
# `create`

Creates a project directory with a minimal `apibackuper.cfg` containing the
`settings` section. Configure the endpoint before running other commands.

```bash
apibackuper create etrust
cd etrust
# save a complete apibackuper.yaml, using a template or the quick start
apibackuper validate-config
apibackuper run full --dry-run
```

**Arguments:**

- `name` — project directory name

`--verbose` / `-v` enables console logging.

## Configure the generated project

Save `apibackuper.yaml` using the [quick start](/getting-started/quick-start)
or a [template](/examples/templates). YAML takes precedence over the generated
INI file, which can then be removed. For POST APIs, also create `params.json`.

`--url` / `-u`, `--config` / `-c`, `--http-mode` / `-m`, `--iterateby` / `-b`,
`--work-modes` / `-w`, `--pagekey` / `-k`, `--pagesize` / `-s`,
`--datakey` / `-d`, `--itemkey` / `-i` and `--changekey` / `-e` are accepted
for compatibility. They currently do not populate or select the configuration.
Set the corresponding YAML fields explicitly. With `--url`, the CLI prints
a reminder to edit the configuration manually.

To generate YAML from a live URL, use [`detect --url URL --write-config`](/commands/detect)
and review its suggestions. Detection makes HTTP requests; `create` does not.
