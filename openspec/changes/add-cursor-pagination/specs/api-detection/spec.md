## ADDED Requirements
### Requirement: Cursor mode detection
`apibackuper detect` SHALL suggest `iterate_by: next_url` with `data.next_url_key`
when the sampled JSON response contains a next-link field such as `next`,
`links.next` or `@odata.nextLink`, `iterate_by: cursor` with
`data.next_cursor_key` for fields such as `next_cursor` or `cursor.next`, and
`iterate_by: link_header` when the response has a `Link` header with
`rel="next"`.

#### Scenario: Next link in body
- **WHEN** the sample response is `{"results": [...], "next": "https://api.example/items?page=2"}`
- **THEN** detect suggests `iterate_by: next_url` and `next_url_key: next`

#### Scenario: Link header present
- **WHEN** the sample response has `Link: <https://api.example/items?page=2>; rel="next"`
- **THEN** detect suggests `iterate_by: link_header`
