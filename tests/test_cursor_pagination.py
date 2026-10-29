"""Cursor, next-URL and Link-header pagination (openspec add-cursor-pagination)."""

import pytest
from requests.structures import CaseInsensitiveDict

from apibackuper.cmds.project import apply_detected_options
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
reply, stored = workflow.reply, workflow.stored

CURSOR = {
    "project": {"iterate_by": "cursor"},
    "params": {"cursor_param": "cursor"},
    "data": {"next_cursor_key": "meta.next"},
}
NEXT_URL = {"project": {"iterate_by": "next_url"}, "data": {"next_url_key": "next"}}


def cursor_project(make_project, sections=CURSOR, **extra):
    merged = {name: dict(values) for name, values in sections.items()}
    for name, values in extra.items():
        merged.setdefault(name, {}).update(values)
    builder = make_project(**merged)
    builder.total_number_key = ""
    return builder


def serve_cursors(builder, pages):
    """Answer each request from ``pages`` keyed by the cursor it carries."""

    def get(url, **kwargs):
        return reply(pages[kwargs.get("params", {}).get("cursor")])

    builder.http.get.side_effect = get


def sent_cursors(builder):
    return [call.kwargs["params"].get("cursor") for call in builder.http.get.call_args_list]


def with_link(payload, target=None):
    response = reply(payload)
    response.headers = CaseInsensitiveDict({"Link": f'<{target}>; rel="next"'} if target else {})
    return response


def test_cursor_chain_runs_until_no_token(make_project):
    builder = cursor_project(make_project)
    serve_cursors(
        builder,
        {
            None: {"items": [{"id": 1}, {"id": 2}], "meta": {"next": "a"}},
            # A short page with a token does not end a cursor run.
            "a": {"items": [{"id": 3}], "meta": {"next": "b"}},
            "b": {"items": [{"id": 4}, {"id": 5}], "meta": {}},
        },
    )
    builder.run("full")
    assert [item["id"] for item in stored(builder)] == [1, 2, 3, 4, 5]
    assert sent_cursors(builder) == [None, "a", "b"]


def test_next_url_is_resolved_and_sent_without_base_params(make_project):
    builder = cursor_project(make_project, NEXT_URL)
    builder.http.get.side_effect = [
        reply({"items": [{"id": 1}], "next": "/items?page=2"}),
        reply({"items": [{"id": 2}]}),
    ]
    builder.run("full")
    second = builder.http.get.call_args_list[1]
    assert second.args[0] == "https://api.example.test/items?page=2"
    assert second.kwargs["params"] == {}
    assert [item["id"] for item in stored(builder)] == [1, 2]


def test_odata_next_link_literal_key(make_project):
    builder = cursor_project(
        make_project,
        {"project": {"iterate_by": "next_url"}, "data": {"next_url_key": "@odata.nextLink"}},
    )
    builder.http.get.side_effect = [
        reply({"items": [{"id": 1}], "@odata.nextLink": "https://api.example.test/items?$skip=1"}),
        reply({"items": [{"id": 2}]}),
    ]
    builder.run("full")
    assert builder.http.get.call_args_list[1].args[0].endswith("$skip=1")


def test_link_header_pagination(make_project):
    builder = cursor_project(make_project, {"project": {"iterate_by": "link_header"}})
    builder.http.get.side_effect = [
        with_link({"items": [{"id": 1}]}, "https://api.example.test/items?page=2"),
        with_link({"items": [{"id": 2}]}),
    ]
    builder.run("full")
    assert builder.http.get.call_args_list[1].args[0] == "https://api.example.test/items?page=2"
    assert [item["id"] for item in stored(builder)] == [1, 2]


@pytest.mark.parametrize("allowed", [False, True])
def test_cross_host_next_url(make_project, allowed):
    builder = cursor_project(make_project, NEXT_URL, params={"allow_cross_host_next": allowed})
    builder.http.get.side_effect = [
        reply({"items": [{"id": 1}], "next": "https://other.example.test/items?page=2"}),
        reply({"items": [{"id": 2}]}),
    ]
    if allowed:
        builder.run("full")
        assert builder.http.get.call_args_list[1].args[0].startswith("https://other.example.test/")
    else:
        with pytest.raises(RuntimeError, match="another host"):
            builder.run("full")
        assert builder.http.get.call_count == 1
        assert not builder._load_state()


def test_repeated_cursor_fails_as_incomplete(make_project):
    builder = cursor_project(make_project)
    serve_cursors(
        builder,
        {
            None: {"items": [{"id": 1}], "meta": {"next": "a"}},
            "a": {"items": [{"id": 2}], "meta": {"next": "a"}},
        },
    )
    with pytest.raises(RuntimeError, match="already followed"):
        builder.run("full")
    assert not builder._load_state()


def test_interrupted_cursor_run_resumes_from_stored_cursor(make_project):
    builder = cursor_project(make_project)
    pages = {
        None: {"items": [{"id": 1}], "meta": {"next": "a"}},
        "a": {"items": [{"id": 2}], "meta": {"next": "b"}},
        "b": {"items": [{"id": 3}], "meta": {}},
    }

    def interrupted(url, **kwargs):
        if kwargs["params"].get("cursor") == "b":
            raise KeyboardInterrupt
        return reply(pages[kwargs["params"].get("cursor")])

    builder.http.get.side_effect = interrupted
    with pytest.raises(KeyboardInterrupt):
        builder.run("full")
    checkpoint = builder._load_checkpoint()
    assert checkpoint["next_page"] == 3 and checkpoint["cursor"] == "b"
    builder.http.get.reset_mock()
    serve_cursors(builder, pages)
    builder.run("full", resume=True)
    assert sent_cursors(builder) == ["b"]
    assert [item["id"] for item in stored(builder)] == [1, 2, 3]


def test_legacy_checkpoint_without_cursor_replays_chain(make_project):
    builder = cursor_project(make_project)
    pages = {
        None: {"items": [{"id": 1}], "meta": {"next": "a"}},
        "a": {"items": [{"id": 2}], "meta": {}},
    }
    serve_cursors(builder, pages)
    builder.run("full")
    checkpoint = dict(builder._load_checkpoint(), status="running", next_page=2)
    checkpoint.pop("cursor")
    builder._save_checkpoint(checkpoint)
    builder.http.get.reset_mock()
    builder.run("full", resume=True)
    assert sent_cursors(builder) == [None, "a"]


def test_next_url_update_sends_watermark_only_first(make_project):
    builder = cursor_project(
        make_project,
        NEXT_URL,
        project={"update_mode": "by_timestamp"},
        params={"update_since_param": "since"},
    )
    builder.http.get.side_effect = [reply({"items": [{"id": 1}]})]
    builder.run("full")
    builder.http.get.reset_mock()
    builder.http.get.side_effect = [
        reply({"items": [{"id": 2}], "next": "/items?since=x&page=2"}),
        reply({"items": [{"id": 3}]}),
    ]
    builder.update()
    first, second = builder.http.get.call_args_list
    assert "since" in first.kwargs["params"]
    assert second.kwargs["params"] == {}


def test_cursor_configuration_is_validated(make_project):
    parallel = cursor_project(make_project, request={"parallelism": 4})
    valid, errors, _ = parallel.validate_config()
    assert not valid and errors == 1
    missing = cursor_project(make_project, {"project": {"iterate_by": "cursor"}})
    valid, errors, _ = missing.validate_config()
    assert not valid and errors == 2
    with pytest.raises(ValueError, match="run continue"):
        cursor_project(make_project).run("continue")


@pytest.mark.parametrize(
    "payload,headers,expected",
    [
        (
            {"results": [], "next": "https://api.example.test/items?page=2"},
            {},
            {"iterate_by": "next_url", "next_url_key": "next"},
        ),
        (
            {"items": [], "response_metadata": {"next_cursor": "abc"}},
            {},
            {
                "iterate_by": "cursor",
                "next_cursor_key": "response_metadata.next_cursor",
                "cursor_param": "cursor",
            },
        ),
        (
            {"items": [], "page": 1},
            {"Link": '<https://api.example.test/items?page=2>; rel="next"'},
            {"iterate_by": "link_header"},
        ),
    ],
)
def test_detect_suggests_cursor_modes(make_project, payload, headers, expected):
    builder = make_project()
    suggestions = builder._detect_suggestions(payload, CaseInsensitiveDict(headers))
    assert {key: suggestions[key] for key in expected} == expected


def test_detect_writes_cursor_options():
    config = {"data": {"data_key": "items"}, "project": {"url": "https://x.test"}}
    apply_detected_options(
        config,
        {"iterate_by": "cursor", "next_cursor_key": "meta.next", "cursor_param": "cursor"},
    )
    assert config["params"] == {"cursor_param": "cursor"}
    assert config["data"]["next_cursor_key"] == "meta.next"
    assert config["project"]["iterate_by"] == "cursor"
