"""Tests for the extracted ``cmds.export`` module.

These cover the per-record filter / project / serialise pipeline that
lives in :func:`process_record`. The orchestrator (``ProjectBuilder.export``)
opens the storage backend and iterates over its files; the helper does
the per-record work.
"""
import json
import pytest

from apibackuper.cmds.export import process_record, serialize_record
from apibackuper.cmds.where_filter import parse_where


def _where_pred(expression: str):
    cond = parse_where(expression)
    if cond is None:
        return lambda rec: True
    from apibackuper.cmds.where_filter import match_where
    return lambda rec: match_where(rec, cond)


class TestProcessRecordBasic:
    def test_empty_data_returns_empty_list(self):
        assert process_record(None, data_key=None, where=None) == []

    def test_top_level_list_passes_through(self):
        data = [{"a": 1}, {"a": 2}]
        result = process_record(data, data_key=None, where=None)
        assert result == [{"a": 1}, {"a": 2}]

    def test_top_level_dict_treated_as_one_record(self):
        # A bare dict (no data_key, no list) is treated as a single record.
        data = {"a": 1}
        result = process_record(data, data_key=None, where=None)
        assert result == [{"a": 1}]

    def test_data_key_with_list(self):
        data = {"results": [{"a": 1}, {"a": 2}]}
        result = process_record(data, data_key="results", where=None)
        assert result == [{"a": 1}, {"a": 2}]

    def test_data_key_with_single_dict(self):
        # A single dict value at data_key is wrapped as a one-item list.
        data = {"results": {"a": 1}}
        result = process_record(data, data_key="results", where=None)
        assert result == [{"a": 1}]

    def test_data_key_missing_returns_empty(self):
        data = {"unrelated": 1}
        result = process_record(data, data_key="missing", where=None)
        assert result == []

    def test_data_key_dotted_path(self):
        data = {"meta": {"records": [{"x": 1}]}}
        result = process_record(data, data_key="meta.records", where=None)
        assert result == [{"x": 1}]


class TestProcessRecordFiltering:
    def test_where_filter_accepts_subset(self):
        data = [{"count": 1}, {"count": 5}, {"count": 10}]
        result = process_record(
            data,
            data_key=None,
            where=_where_pred("count > 3"),
        )
        assert result == [{"count": 5}, {"count": 10}]

    def test_where_no_match(self):
        data = [{"count": 1}, {"count": 2}]
        result = process_record(
            data,
            data_key=None,
            where=_where_pred("count > 100"),
        )
        assert result == []


class TestProcessRecordProjection:
    def test_fields_projects_to_dotted_paths(self):
        data = {"a": 1, "b": 2, "c": 3}
        result = process_record(
            data,
            data_key=None,
            fields=["a", "b"],
            where=None,
        )
        assert result == [{"a": 1, "b": 2}]

    def test_fields_none_returns_original(self):
        data = {"a": 1, "b": 2}
        result = process_record(
            data,
            data_key=None,
            fields=None,
            where=None,
        )
        assert result == [{"a": 1, "b": 2}]

    def test_fields_preserves_falsy_values(self):
        # A 0 in the source must round-trip, not be silently dropped.
        data = {"a": 0, "b": False, "c": ""}
        result = process_record(
            data,
            data_key=None,
            fields=["a", "b", "c"],
            where=None,
        )
        assert result == [{"a": 0, "b": False, "c": ""}]

    def test_fields_dotted_path_into_nested_dict(self):
        data = {"meta": {"count": 5, "inner": "x"}, "other": 1}
        result = process_record(
            data,
            data_key=None,
            fields=["meta.count"],
            where=None,
        )
        assert result == [{"meta.count": 5}]


class TestSerializeRecord:
    def test_basic_dict_renders_as_jsonl(self):
        out = serialize_record({"a": 1})
        assert out == '{"a": 1}\n'

    def test_unicode_preserved(self):
        out = serialize_record({"name": "тест"})
        assert out == '{"name": "тест"}\n'
        # Must be valid JSON.
        parsed = json.loads(out)
        assert parsed == {"name": "тест"}

    def test_round_trip(self):
        original = {"a": 1, "b": [1, 2, 3], "c": {"nested": True}}
        round_tripped = json.loads(serialize_record(original))
        assert round_tripped == original


class TestRecordFilter:
    """The follow-mode path passes an additional ``record_filter`` callback
    that excludes the whole payload when the followed data is missing."""

    def test_record_filter_rejects_entire_payload(self):
        data = {"records": [{"a": 1}]}

        def reject(rec):
            return "required_marker" in rec

        result = process_record(
            data,
            data_key="records",
            record_filter=reject,
            where=None,
        )
        assert result == []

    def test_record_filter_accepts_payload(self):
        data = {"records": [{"a": 1}]}

        def accept(rec):
            return True

        result = process_record(
            data,
            data_key="records",
            record_filter=accept,
            where=None,
        )
        assert result == [{"a": 1}]