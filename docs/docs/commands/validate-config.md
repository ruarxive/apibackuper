---
title: "validate-config"
description: "apibackuper validate-config command reference"
---
# `validate-config`

Validates the project YAML/INI against the JSON schema and prints errors.

```bash
apibackuper validate-config
apibackuper validate-config -p hhemployers
apibackuper validate-config --verbose
```

Exits `0` when the configuration is valid, `1` otherwise.

The schema lives in `apibackuper/schemas/config_schema.json`. See
[Configuration reference](/configuration/reference).
