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
overwrite an existing file when used with `--url`.

Typical suggestions include `data_key`, `total_number_key`, and `iterate_by`.

Example: `examples/features/detect/`.
