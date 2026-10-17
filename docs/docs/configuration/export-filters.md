---
title: "Export filters"
description: "The exact --where and --fields grammar, types, missing values and date comparisons"
---
# Export filters

Export filters operate on **saved records**, without contacting the API. They
do not change backup contents, pagination or which objects the server returns.
Use request parameters for server-side filtering and these options for an
exported subset.

`export --where` accepts one comparison:

```text
FIELD OP VALUE
```

| Part | Accepted syntax |
|------|-----------------|
| `FIELD` | A record field or nested path such as `metadata.score`; no spaces or parentheses |
| `OP` | `==`, `!=`, `<`, `<=`, `>`, `>=` |
| `VALUE` | Integer, decimal, or text; optional matching single/double quotes |

Quote the whole expression for your shell:

```bash
apibackuper export selected.jsonl --where "id >= 3"
apibackuper export selected.jsonl --where "metadata.score < 50"
apibackuper export selected.jsonl --where "title == 'Item 3'"
apibackuper export recent.jsonl --where "updated_at >= 2026-01-03"
```

Text containing comparison symbols, quotes of the other kind, parentheses or
the words AND/OR/NOT needs matching quotes around the value, for example
`--where "title == 'Research AND Development'"`. Embedded quotes matching the
value delimiter and backslash escape sequences are not supported by the filter
parser. Use the other delimiter or transform the exported data downstream.

## Values and comparisons

- Values parse as integers, then as decimals when they contain `.`. Matching
  quotes are stripped before this conversion, so `'123'` also becomes a number.
- Other values are strings. `true`, `false` and `null` are strings, not JSON
  boolean/null literals. There is no boolean or null literal syntax.
- A missing field or JSON `null` never matches, including `!=` conditions.
- Equality uses the decoded JSON/Python value types; numeric `3` differs from
  string `"3"`. Ordering between incompatible types does not match.
- Dates/timestamps compare as **strings**, without date parsing or timezone
  conversion. Lexicographic order is chronological only with a consistently
  normalized representation. Normalize offsets, precision and date format first.
- Nested field lookup uses `settings.splitter`, default `.`.

There are no logical expressions (`AND`, `OR`, `NOT`), chained comparisons,
parentheses, SQL `=`, `IN`, wildcard matching or regular expressions. Invalid
expressions exit with status 1 before replacing existing export output. An empty
filter string means no filter. To combine conditions, filter downstream or use
an API-side query in [params.json](/configuration/http-requests).

## Selecting fields

```bash
apibackuper export selected.jsonl --fields id,metadata.score --where "id >= 3"
```

Filtering runs before projection. Selected nested paths become literal output
keys: `metadata.score` produces `{"metadata.score": 30}`, not a nested object.
Missing and null-valued selected fields are omitted; `0`, `false` and empty
strings are preserved. Selecting no fields leaves the original record intact.

Neither option deduplicates update history. See [export](/commands/export) for
source selection, retained generations and output safety.


## Worked input and output

Assume the extracted records are:

```json
[
  {"id":41,"title":"First","metadata":{"score":10}},
  {"id":42,"title":"Second","metadata":{"score":30}},
  {"id":43,"title":"Third"}
]
```

Run:

```bash
apibackuper export selected.jsonl --where "id >= 42" --fields id,title,metadata.score
```

The JSON Lines output is:

```jsonl
{"id":42,"title":"Second","metadata.score":30}
{"id":43,"title":"Third"}
```

Both IDs satisfy the condition. ID 43 remains present even though the selected
score field is missing; the missing output key is simply omitted. The filter
can read fields that are not included in `--fields` because filtering happens
before projection.

## Missing values and numeric-looking strings

| Record field | Condition | Result |
|--------------|-----------|--------|
| `score: 0` | `score == 0` | Match |
| `score: null` or missing | `score != 0` | No match |
| `id: "42"` (JSON string) | `id == 42` | No match |
| `id: "42"` | `id == '42'` | No match; quoting does not disable numeric conversion |
| `updated_at: "2026-01-03"` | `updated_at >= 2026-01-02` | String comparison matches this normalized date format |

The table uses shorthand for record values, not separate configuration fields.
Boolean record values follow Python comparison rules and may compare equal to
numeric 0/1; there is no distinct typed-boolean filter literal. For identifiers
stored as numeric-looking strings, explicit date parsing, null predicates or
compound conditions, perform the transformation/filter downstream.

## Shell quoting and invalid expressions

The shell must pass the expression as one argument. For a text value with
spaces, use outer double quotes and inner single quotes:

```bash
apibackuper export selected.jsonl --where "title == 'Item 42'"
```

`id = 42`, `id >` and `id > 1 AND id < 50` are invalid filters. They fail with
status 1 rather than creating an unfiltered or misleading export. Existing
output is preserved on failure. In Python, pass `where="id >= 42"` and a list
such as `fields=["id", "title"]`; the shell quoting layer is not needed.

Field paths use object keys and the configured splitter, not JSONPath, array
index expressions or SQL. Projecting `metadata.score` deliberately produces a
flat output key of that name. Need nested output objects or a latest-version
view of update history? Export the required fields and transform them downstream.

## Quick checks

| Unexpected result | Likely explanation |
|-------------------|--------------------|
| No rows match a visible ID | Source ID is a string, while filter value was converted to a number |
| Nulls remain absent with `!=` | Missing/null fields never match a condition |
| Date boundary seems wrong | Mixed timezone offsets, precision or non-normalized string formats |
| A nested field disappears | It was missing/null in that record, or the configured splitter differs |
| Repeated IDs remain | Filtering/projection do not deduplicate retained generations |
| Records differ from list backup | An existing unnamed follow details archive is selected for export |
