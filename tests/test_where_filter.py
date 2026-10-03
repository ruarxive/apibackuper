"""Tests for the extracted ``cmds.where_filter`` module.

These lock in the behaviour that used to live inline in
``ProjectBuilder._parse_where`` / ``_match_where`` / ``_select_fields``.
"""
import pytest

from apibackuper.cmds.where_filter import parse_where, match_where, select_fields


class TestParseWhere:
    def test_empty_returns_none(self):
        assert parse_where("") is None
        assert parse_where(None) is None

    def test_int_value(self):
        cond = parse_where("count > 10")
        assert cond == {"field": "count", "op": ">", "value": 10, "splitter": "."}

    def test_float_value(self):
        cond = parse_where("rate >= 1.5")
        assert cond["value"] == 1.5

    def test_string_value_for_iso_date(self):
        cond = parse_where("updated_at >= 2024-01-01")
        assert cond["value"] == "2024-01-01"
        assert cond["op"] == ">="

    def test_quoted_value(self):
        cond = parse_where("name == \"alice\"")
        assert cond["value"] == "alice"

    def test_inequality_operator(self):
        cond = parse_where("status != 200")
        assert cond["op"] == "!="
        assert cond["value"] == 200

    def test_no_operator_returns_none(self):
        # No recognised comparison operator -> unparseable
        assert parse_where("just_a_word") is None

    def test_dotted_field_path(self):
        cond = parse_where("meta.count == 5")
        assert cond["field"] == "meta.count"
        assert cond["value"] == 5

    def test_splitter_propagated(self):
        # Splitter only affects how ``field`` is resolved at match-time, not
        # the parse output. A semicolon-style nested key like ``a;b`` still
        # uses ``>`` as the operator.
        cond = parse_where("a;b > 1", splitter=";")
        assert cond["splitter"] == ";"
        assert cond["op"] == ">"
        assert cond["field"] == "a;b"
        assert cond["value"] == 1

    def test_longest_operator_wins(self):
        # ``<=`` must be matched before ``<``.
        cond = parse_where("x <= 5")
        assert cond["op"] == "<="


class TestMatchWhere:
    def test_no_condition_matches_anything(self):
        assert match_where({"a": 1}, None) is True
        assert match_where({}, {}) is True

    def test_equality(self):
        cond = parse_where("count == 5")
        assert match_where({"count": 5}, cond) is True
        assert match_where({"count": 4}, cond) is False

    def test_inequality(self):
        cond = parse_where("count != 5")
        assert match_where({"count": 4}, cond) is True
        assert match_where({"count": 5}, cond) is False

    def test_missing_field_does_not_match(self):
        cond = parse_where("missing == 1")
        assert match_where({"other": 1}, cond) is False

    def test_comparison_with_incompatible_types_does_not_raise(self):
        cond = parse_where("count > 5")
        # ``dict > int`` raises TypeError inside match_where, must be caught.
        assert match_where({"count": {"a": 1}}, cond) is False

    def test_string_field_compare(self):
        cond = parse_where("name == alice")
        assert match_where({"name": "alice"}, cond) is True
        assert match_where({"name": "bob"}, cond) is False


class TestSelectFields:
    def test_no_fields_returns_original(self):
        item = {"a": 1, "b": 2}
        assert select_fields(item, None) is item
        assert select_fields(item, []) is item

    def test_single_field(self):
        result = select_fields({"a": 1, "b": 2}, ["a"])
        assert result == {"a": 1}

    def test_dotted_path(self):
        result = select_fields({"meta": {"count": 5}}, ["meta.count"])
        assert result == {"meta.count": 5}

    def test_missing_field_excluded(self):
        result = select_fields({"a": 1}, ["a", "missing"])
        assert result == {"a": 1}

    def test_falsy_value_preserved(self):
        # Falsy values must round-trip — a 0 in the source is a 0 in the
        # output, not silently dropped.
        result = select_fields({"a": 0, "b": False, "c": ""}, ["a", "b", "c"])
        assert result == {"a": 0, "b": False, "c": ""}

    def test_custom_splitter(self):
        result = select_fields({"a": {"b": 5}}, ["a;b"], splitter=";")
        assert result == {"a;b": 5}