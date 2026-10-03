"""Tests for the extracted ``cmds.fetch`` module.

The helper owns the per-page request parameter assembly for the
configured iteration mode. The HTTP call itself remains in
``ProjectBuilder._single_request`` because of the rate-limiter, auth,
and OAuth2-retry logic that wraps it.
"""
from apibackuper.cmds.utils import _url_replacer
from apibackuper.common import update_dict_values

from apibackuper.cmds.fetch import build_page_request


class TestBuildPageRequestPageMode:
    """``iterate_by == 'page'`` is the canonical mode."""

    def test_page_one_returns_first_page(self):
        url, params, url_params, flatten = build_page_request(
            target_page=1,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="skip",
            count_from_param="from",
            count_to_param="to",
            iterate_by="page",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        assert url == "https://api.example.com/items"
        assert params["page"] == 1
        assert params["size"] == 10

    def test_page_three_includes_page_size(self):
        _, params, _, _ = build_page_request(
            target_page=3,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=50,
            page_size_param="per_page",
            page_number_param="page",
            count_skip_param="skip",
            count_from_param="from",
            count_to_param="to",
            iterate_by="page",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        assert params["page"] == 3
        assert params["per_page"] == 50

    def test_change_params_not_mutated(self):
        # The function returns a copy; the caller's dict is unchanged.
        change_params = {"existing": "value"}
        _, _, _, _ = build_page_request(
            target_page=2,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="skip",
            count_from_param="from",
            count_to_param="to",
            iterate_by="page",
            change_params=change_params,
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        assert "page" not in change_params  # caller-side dict untouched
        assert "size" not in change_params


class TestBuildPageRequestSkipMode:
    def test_skip_mode_uses_offset(self):
        _, params, _, _ = build_page_request(
            target_page=4,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=25,
            page_size_param="",
            page_number_param="",
            count_skip_param="offset",
            count_from_param="",
            count_to_param="",
            iterate_by="skip",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        # page 4 with size 25 -> skip 75
        assert params["offset"] == 75

    def test_skip_mode_page_one_zero_offset(self):
        _, params, _, _ = build_page_request(
            target_page=1,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=10,
            page_size_param="",
            page_number_param="",
            count_skip_param="offset",
            count_from_param="",
            count_to_param="",
            iterate_by="skip",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        assert params["offset"] == 0


class TestBuildPageRequestRangeMode:
    def test_range_mode_uses_from_and_to(self):
        _, params, _, _ = build_page_request(
            target_page=2,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=20,
            page_size_param="",
            page_number_param="",
            count_skip_param="",
            count_from_param="from",
            count_to_param="to",
            iterate_by="range",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        # page 2 with size 20 -> from=20, to=40
        assert params["from"] == 20
        assert params["to"] == 40


class TestBuildPageRequestQueryModeParams:
    def test_query_mode_params_writes_to_url(self):
        url, _, url_params, _ = build_page_request(
            target_page=1,
            start_url="https://api.example.com/items",
            query_mode="params",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="",
            count_from_param="",
            count_to_param="",
            iterate_by="page",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        # Path-style URL with semicolon delimiter.
        assert ";page=1" in url
        assert ";size=10" in url
        assert url_params["page"] == 1
        assert url_params["size"] == 10

    def test_query_mode_mixed_uses_url_encoding(self):
        url, _, url_params, _ = build_page_request(
            target_page=1,
            start_url="https://api.example.com/items",
            query_mode="mixed",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="",
            count_from_param="",
            count_to_param="",
            iterate_by="page",
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        assert url.startswith("https://api.example.com/items?")
        assert "page=1" in url
        assert url_params["page"] == 1


class TestBuildPageRequestFlatParams:
    def test_flat_params_produces_stringified_dict(self):
        _, _, _, flatten = build_page_request(
            target_page=1,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="",
            count_from_param="",
            count_to_param="",
            iterate_by="page",
            change_params={},
            base_params={"token": "abc"},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=True,
        )
        # All values coerced to str.
        assert flatten["page"] == "1"
        assert flatten["size"] == "10"
        assert flatten["token"] == "abc"


class TestBuildPageRequestFallback:
    def test_unknown_iterate_by_falls_back_to_page(self):
        _, params, _, _ = build_page_request(
            target_page=5,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="",
            count_from_param="",
            count_to_param="",
            iterate_by="garbage",  # unknown mode
            change_params={},
            base_params={},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        # The fallback is "page", which sets `page_number_param`.
        assert params["page"] == 5


class TestBuildPageRequestBaseParamsMerged:
    def test_base_params_preserved(self):
        _, params, _, _ = build_page_request(
            target_page=2,
            start_url="https://api.example.com/items",
            query_mode="url",
            page_limit=10,
            page_size_param="size",
            page_number_param="page",
            count_skip_param="",
            count_from_param="",
            count_to_param="",
            iterate_by="page",
            change_params={},
            base_params={"token": "abc", "filter": "active"},
            base_url_params=None,
            base_flatten=None,
            url_replacer=_url_replacer,
            update_dict_values=update_dict_values,
            flat_params=False,
        )
        # base_params retained + page params appended.
        assert params["token"] == "abc"
        assert params["filter"] == "active"
        assert params["page"] == 2
        assert params["size"] == 10