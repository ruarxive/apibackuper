---
title: "schema"
description: "apibackuper schema command reference"
---
# `schema`

Prints the configuration JSON Schema that `validate-config` applies to
`apibackuper.yaml`.

```bash
apibackuper schema
apibackuper schema > apibackuper.schema.json
```

Use it to look up allowed sections, field names, types and enumerations, or to
validate configurations in an editor. The file is also shipped in the package
as `apibackuper/schemas/config_schema.json`.
