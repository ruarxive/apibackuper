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

Requires `data.total_number_key` to obtain the total count from the response
and a positive `params.page_size_limit`. Configure `data.data_key` for wrapped
record arrays. This command samples the live endpoint; its `mode` argument
does not apply incremental update filters.

For an offline plan based on configuration and saved state, use
[`run full --dry-run`](/commands/run). Its estimate can be a lower bound or
unknown when no total count is available.

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
the project config apply. The size and time figures are estimates from the
sample response and can change during a long backup.
