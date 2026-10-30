---
title: "detect"
description: "apibackuper detect command reference"
---
# `detect`

Inspects an API response and suggests pagination / data keys.

```bash
# Against an existing project
apibackuper detect -p myproject
apibackuper detect --write-config -p myproject

# From a URL (prints or writes YAML)
apibackuper detect --url https://api.example.com/v1/items
apibackuper detect --url https://api.example.com/v1/items --write-config
```

`--write-config` writes suggestions into `apibackuper.yaml`. It will not
overwrite an existing file when used with `--url`, and it never replaces an
option the project already sets.

Typical suggestions include `data_key`, `total_number_key`, and `iterate_by`.
Unless the project already sets the parameter for its pagination mode, detect
also probes the endpoint with a few extra requests and suggests
`page_number_param` or `count_skip_param`, `page_size_param` and
`page_size_limit`. A parameter is accepted only when page 2 (or the next
offset) returns other records and the requested size is honoured. The output
also lists `fields`, a `sample_record` and `warnings`. With `--url`, detected
pagination parameters are removed from the URL's query string.

To create a project directory with request files and authentication in one
step, use [`init`](/commands/init).

Example: `examples/features/detect/`.
