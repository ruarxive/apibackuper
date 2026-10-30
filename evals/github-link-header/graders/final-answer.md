---
type: llm
---

PASS if the final reply hands over an apibackuper project (an apibackuper.yaml
file, plus request files or hooks if needed) and names the commands to rerun the
collection and export, such as `apibackuper run full` and `apibackuper export`.
FAIL if the collection is implemented as a custom HTTP pagination loop in
Python or another language, or if the reply gives no way to rerun it.
