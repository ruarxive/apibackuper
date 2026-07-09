## 1. Rewrite Weak CLI Tests
- [ ] 1.1 Replace all `assert result.exit_code in [0, 1]` with specific assertions
- [ ] 1.2 Add assertions for expected output content in each command test
- [ ] 1.3 Verify mock call arguments instead of just `called`
- [ ] 1.4 Remove bare `except: pass` blocks that silently accept failures

## 2. Core Logic Tests
- [ ] 2.1 Add `test_run_paginated()` — mock HTTP multi-page response, verify all pages stored
- [ ] 2.2 `test_run_single_page()` — single page, no pagination needed
- [ ] 2.3 `test_follow_item_mode()` — mock index + follow-up responses
- [ ] 2.4 `test_follow_url_mode()` — follow by URL pattern
- [ ] 2.5 `test_export_jsonl()` — verify output format and record count
- [ ] 2.6 `test_export_parquet()` — verify parquet output with pandas
- [ ] 2.7 `test_update_incremental()` — state file save/load, only new records fetched

## 3. Edge Case Tests
- [x] 3.1 `test_pagination_non_divisible_total()` — total=100, limit=30 → 4 pages (verified by integer division fix)
- [x] 3.2 `test_url_replacer_non_query_mode_no_question_mark()` — verifies fix
- [ ] 3.3 `test_retry_on_500()` — mock transient failure then success
- [ ] 3.4 `test_retry_with_retry_after()` — honor Retry-After header
- [ ] 3.5 `test_rate_limiter_all_limits()` — all three limits active simultaneously
- [ ] 3.6 `test_rate_limiter_zero_limit()` — requests_per_second=0
- [x] 3.7 `test_filesystem_storage_path_traversal()` — reject `../` in paths
- [ ] 3.8 `test_storage_empty_content()` — store and retrieve empty bytes
- [ ] 3.9 `test_storage_binary_content()` — store and retrieve non-UTF-8 data
- [x] 3.10 `test_sqlite_invalid_table_name()` — SQL injection prevention

## 4. Negative Tests
- [ ] 4.1 `test_config_file_missing()` — graceful error, non-zero exit
- [ ] 4.2 `test_config_invalid_yaml()` — parse error handling
- [ ] 4.3 `test_network_timeout()` — connection timeout recovery
- [ ] 4.4 `test_permission_error()` — cannot write to storage path

## 5. Coverage
- [ ] 5.1 Measure coverage with coverage.py
- [ ] 5.2 Identify uncovered branches in `project.py`
- [ ] 5.3 Add tests until coverage >= 80% for `project.py`
