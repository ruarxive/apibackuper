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
apibackuper validate-config --json
```

Exits `0` when the configuration has no errors; warnings are allowed by default.
`--strict` makes warnings fail with exit status `1` as well. Loading a legacy
INI configuration produces a deprecation warning.

Missing or invalid project settings, including unresolved required environment
variables, exit with status `1`. Use `--verbose` for detailed validation output.
Execution commands such as `run full` can report an unresolved variable with
status `2`; validation and offline plans instead fail their configuration check.

A warning names any pagination parameter the selected `iterate_by` mode needs
but the configuration lacks (`params.page_number_param` for `page`,
`params.count_skip_param` for `skip`, `count_from_param`/`count_to_param` for
`range`). Without it a run saves only the first page.

`--json` prints the result with the configuration path and a hint for each
problem; exit statuses are the same as in text mode:

```json
{
  "valid": true,
  "errors": [],
  "warnings": [
    {
      "path": "params.page_number_param",
      "message": "params.page_number_param not set for iterate_by: page; only the first page will be collected",
      "hint": "Set it to the API's pagination parameter name, or run 'apibackuper detect' to probe it"
    }
  ]
}
```

The schema lives in `apibackuper/schemas/config_schema.json`; print it with
[`apibackuper schema`](/commands/schema). See
[Configuration reference](/configuration/reference).
