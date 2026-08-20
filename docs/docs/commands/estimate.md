---
title: "estimate"
description: "apibackuper estimate command reference"
---
# `estimate`

Samples the API and reports record counts, expected size, and time.

```bash
apibackuper estimate full
apibackuper estimate full -p budgettofk
```

**Arguments:**

- `mode` — estimate mode (default `full`)

Typical output:

```text
Total records: 12282
Records per request: 500
Total requests: 25
Average record size 1293.60 bytes
Estimated size (json lines) 15.89 MB
Avg request time, seconds 1.8015
Estimated all requests time, seconds 46.0536
```

Run estimate before any large `run`. SSL, auth, and rate-limit settings from
the project config apply.
