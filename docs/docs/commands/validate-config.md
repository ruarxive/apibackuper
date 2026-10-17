---
title: "validate-config"
description: "apibackuper validate-config command reference"
---
# `validate-config`

Checks required project settings and applies the bundled JSON schema to YAML
configuration. Validation does not contact the API.

```bash
apibackuper validate-config
apibackuper validate-config -p hhemployers
apibackuper validate-config --verbose
apibackuper validate-config --strict
```

Exits `0` when the configuration has no errors; warnings are allowed by default.
`--strict` makes warnings fail with exit status `1` as well. Loading a legacy
INI configuration produces a deprecation warning.

Missing or invalid project settings, including unresolved required environment
variables, exit with status `1`. Use `--verbose` for detailed validation output.
Execution commands such as `run full` can report an unresolved variable with
status `2`; validation and offline plans instead fail their configuration check.

The schema lives in `apibackuper/schemas/config_schema.json`. See
[Configuration reference](/configuration/reference).
