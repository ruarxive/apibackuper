## 1. Bug Fixes
- [x] 1.1 Fix integer division (`/` → `//`) at project.py:1556 and project.py:2846
- [x] 1.2 Remove dead no-op branch (project.py:1597-1598)
- [x] 1.3 Fix change-key comparison to use natural types (project.py:1747-1749)
- [x] 1.4 Fix `_url_replacer` non-query mode query-char logic (utils.py:30-41)
- [x] 1.5 Add `threading.Lock` around shared counters in parallel execution (project.py:1814-1846)
- [x] 1.6 Wrap `list_file` and `skipped_file` in context managers in `getfiles()` (project.py:2594-2616)
- [x] 1.7 Fix duplicate error message construction in `estimate()` (project.py:2769-2834)

## 2. Verification
- [x] 2.1 Add test for page count with non-divisible total
- [x] 2.2 Add test for numeric change-key comparison
- [x] 2.3 Add test for `_url_replacer` in both modes
- [x] 2.4 Add test for parallel execution counter correctness
