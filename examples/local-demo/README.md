# Local API walkthrough

This example serves five fixed records from a Python standard-library HTTP
server on `127.0.0.1`. It requires no credentials or public API access.

From the repository root, start the server in one terminal:

```bash
python examples/local-demo/server.py
```

In another terminal, copy this directory to `demo`, enter it, and follow
`docs/docs/getting-started/quick-start.md`. A page size of 2 produces three
stored pages and five exported records with IDs 1–5. The last page contains
only ID 5. The server also accepts POST pagination as JSON.

Stop the server with Ctrl-C. If port 8765 is occupied, pass `--port 8766` and
change `project.url` in the copied YAML accordingly. The server binds only
the local loopback interface.
