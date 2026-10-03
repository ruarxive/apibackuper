"""Tests for the extracted ``cmds.follow`` module.

The helper owns the *pure* key/URL extraction logic from
``ProjectBuilder.follow``. The orchestrator keeps the HTTP loop and the
destination-archive lifecycle; the helper is responsible for:

* :func:`extract_keys_from_pages` — ``item`` / ``prefix`` modes
* :func:`extract_url_map_from_pages` — ``url`` mode
* :func:`compute_pending_targets` — full vs. continue

Each function takes a zipfile handle so the orchestrator can stay in
charge of opening / closing the archive.
"""
import io
import json
import zipfile

from apibackuper.cmds.follow import (
    _archive_name,
    compute_pending_targets,
    extract_keys_from_pages,
    extract_url_map_from_pages,
)


def _zip_with_pages(pages):
    """Build an in-memory ``ZipFile`` containing one JSON entry per page.

    ``pages`` is an iterable of (filename, dict) tuples. Returns the
    ZipFile handle ready for reading.
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in pages:
            zf.writestr(name, json.dumps(payload))
    buf.seek(0)
    return zipfile.ZipFile(buf, "r")


class TestExtractKeysFromPages:
    """``extract_keys_from_pages`` powers the ``item`` / ``prefix`` modes."""

    def test_simple_list_with_data_key(self):
        zf = _zip_with_pages([
            ("1.json", {"results": [{"id": 10}, {"id": 20}]}),
            ("2.json", {"results": [{"id": 30}]}),
        ])
        keys = extract_keys_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
        )
        assert keys == [10, 20, 30]

    def test_data_key_none_treats_payload_as_iterable(self):
        # When data_key is None the raw payload IS the iterable list.
        zf = _zip_with_pages([
            ("1.json", [{"id": 1}, {"id": 2}]),
        ])
        keys = extract_keys_from_pages(
            zf,
            zf.namelist(),
            data_key=None,
            field_splitter=".",
            item_key="id",
        )
        assert keys == [1, 2]

    def test_dotted_data_key(self):
        zf = _zip_with_pages([
            ("1.json", {"meta": {"records": [{"id": "a"}, {"id": "b"}]}}),
        ])
        keys = extract_keys_from_pages(
            zf,
            zf.namelist(),
            data_key="meta.records",
            field_splitter=".",
            item_key="id",
        )
        assert keys == ["a", "b"]

    def test_page_with_dict_payload_skipped_silently(self):
        # ``prefix`` mode special-case: when ``data_key is None`` the raw
        # payload is iterated; if it's a dict (not a list) the helper
        # silently continues without logging. This is what powers the
        # ``prefix`` branch's tolerance for non-list pages.
        zf = _zip_with_pages([
            ("1.json", {"only": "meta", "no": "list"}),
            ("2.json", [{"id": 1}]),
        ])
        keys = extract_keys_from_pages(
            zf,
            zf.namelist(),
            data_key=None,
            field_splitter=".",
            item_key="id",
        )
        assert keys == [1]

    def test_missing_item_key_logs_skips_page(self):
        # When ``item_key`` is absent on every record, the page yields no
        # keys. (The exception is logged and swallowed.)
        zf = _zip_with_pages([
            ("1.json", {"results": [{"not_id": 1}]}),
            ("2.json", {"results": [{"id": 42}]}),
        ])
        keys = extract_keys_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
        )
        # Page 1 raises KeyError, page 2 contributes.
        assert keys == [42]

    def test_empty_file_list(self):
        zf = _zip_with_pages([])
        keys = extract_keys_from_pages(
            zf,
            [],
            data_key="results",
            field_splitter=".",
            item_key="id",
        )
        assert keys == []

    def test_string_keys_preserved(self):
        zf = _zip_with_pages([
            ("1.json", {"items": [{"slug": "alpha"}, {"slug": "beta"}]}),
        ])
        keys = extract_keys_from_pages(
            zf,
            zf.namelist(),
            data_key="items",
            field_splitter=".",
            item_key="slug",
        )
        assert keys == ["alpha", "beta"]


class TestExtractUrlMapFromPages:
    """``extract_url_map_from_pages`` powers the ``url`` mode."""

    def test_basic_url_extraction(self):
        zf = _zip_with_pages([
            ("1.json", {
                "results": [
                    {"id": 1, "url": "https://api.example.com/a"},
                    {"id": 2, "url": "https://api.example.com/b"},
                ],
            }),
            ("2.json", {
                "results": [
                    {"id": 3, "url": "https://api.example.com/c"},
                ],
            }),
        ])
        url_map = extract_url_map_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
            url_key="url",
        )
        assert url_map == {
            1: "https://api.example.com/a",
            2: "https://api.example.com/b",
            3: "https://api.example.com/c",
        }

    def test_dotted_url_key(self):
        zf = _zip_with_pages([
            ("1.json", {"results": [{"id": 1, "meta": {"link": "https://x"}}]}),
        ])
        url_map = extract_url_map_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
            url_key="meta.link",
        )
        assert url_map == {1: "https://x"}

    def test_page_missing_url_key_writes_none(self):
        # The original ``follow()`` code assigns ``None`` when ``url_key``
        # is absent — the KeyError catch only protects ``item[item_key]``,
        # not the url lookup. The helper preserves that historical
        # behaviour (changing it would be a separate bug-fix commit).
        zf = _zip_with_pages([
            ("1.json", {"results": [{"id": 1}]}),
        ])
        url_map = extract_url_map_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
            url_key="url",
        )
        assert url_map == {1: None}

    def test_page_missing_item_key_logs_skips_page(self):
        # When ``item_key`` is absent on the record, KeyError fires and
        # the whole page is skipped — different from the missing
        # ``url_key`` case above.
        zf = _zip_with_pages([
            ("1.json", {"results": [{"not_id": 1, "url": "x"}]}),
            ("2.json", {"results": [{"id": 2, "url": "https://ok"}]}),
        ])
        url_map = extract_url_map_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
            url_key="url",
        )
        assert url_map == {2: "https://ok"}

    def test_duplicate_id_last_wins(self):
        # If two records share an id, the second one wins — matches the
        # dict-assignment semantics of the original code.
        zf = _zip_with_pages([
            ("1.json", {"results": [
                {"id": 1, "url": "https://first"},
                {"id": 1, "url": "https://second"},
            ]}),
        ])
        url_map = extract_url_map_from_pages(
            zf,
            zf.namelist(),
            data_key="results",
            field_splitter=".",
            item_key="id",
            url_key="url",
        )
        assert url_map == {1: "https://second"}

    def test_empty_file_list(self):
        zf = _zip_with_pages([])
        url_map = extract_url_map_from_pages(
            zf,
            [],
            data_key="results",
            field_splitter=".",
            item_key="id",
            url_key="url",
        )
        assert url_map == {}


class TestComputePendingTargets:
    """``compute_pending_targets`` handles full vs. continue mode."""

    def test_full_mode_returns_all_targets(self):
        # ``full=True`` ignores dest_zip entirely.
        pending, done = compute_pending_targets(
            [1, 2, 3],
            dest_zip=None,
            full=True,
        )
        assert pending == [1, 2, 3]
        assert done == 0

    def test_full_mode_with_dest_zip_still_returns_all(self):
        # Even if a dest_zip is passed, ``full`` wins.
        zf = _zip_with_pages([("1.json", {})])
        pending, done = compute_pending_targets(
            [1, 2, 3],
            dest_zip=zf,
            full=True,
        )
        assert pending == [1, 2, 3]
        assert done == 0

    def test_continue_mode_subtracts_existing(self):
        zf = _zip_with_pages([
            ("1.json", {}),
            ("2.json", {}),
        ])
        pending, done = compute_pending_targets(
            [1, 2, 3, 4],
            dest_zip=zf,
            full=False,
        )
        # Two are already done; only 3 and 4 are pending.
        assert pending == [3, 4]
        assert done == 2

    def test_continue_mode_all_done(self):
        zf = _zip_with_pages([("1.json", {})])
        pending, done = compute_pending_targets(
            [1],
            dest_zip=zf,
            full=False,
        )
        assert pending == []
        assert done == 1

    def test_continue_mode_none_done(self):
        zf = _zip_with_pages([])
        pending, done = compute_pending_targets(
            [1, 2],
            dest_zip=zf,
            full=False,
        )
        assert pending == [1, 2]
        assert done == 0

    def test_full_false_with_none_dest_zip_returns_all(self):
        # When dest_zip is None and full=False, the helper falls back to
        # "return everything" — the orchestrator is in charge of deciding
        # whether the destination should be opened.
        pending, done = compute_pending_targets(
            [1, 2],
            dest_zip=None,
            full=False,
        )
        assert pending == [1, 2]
        assert done == 0

    def test_string_targets(self):
        zf = _zip_with_pages([("alpha.json", {})])
        pending, done = compute_pending_targets(
            ["alpha", "beta", "gamma"],
            dest_zip=zf,
            full=False,
        )
        assert pending == ["beta", "gamma"]
        assert done == 1

    def test_archive_name_internals(self):
        # The private helper is the source of truth for "what name does
        # the orchestrator write to the destination zip?". Locking that
        # down with a test guards the contract that ``compute_pending``
        # and the writer in ``follow()`` agree on the naming convention.
        assert _archive_name(42) == "42.json"
        assert _archive_name("abc-1") == "abc-1.json"