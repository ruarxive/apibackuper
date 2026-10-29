"""Response rules and rate-limit header waits (openspec add-response-rules)."""

import json
import time

import pytest
import requests

from apibackuper.cmds.http_client import RequestFailed
from apibackuper.cmds.response_rules import header_wait, validate_rules
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
reply, serve, stored = workflow.reply, workflow.serve, workflow.stored

RETRY = {"retry_count": 2}
FOLLOW = {
    "follow_mode": "item",
    "follow_item_key": "id",
    "follow_param": "id",
    "follow_pattern": "https://api.example.test/detail",
}


def page(items, total=None):
    return reply({"items": items, "total": len(items) if total is None else total})


def html(status):
    response = reply({}, status)
    response._content = b"<html>maintenance</html>"
    response.headers = requests.structures.CaseInsensitiveDict({"Content-Type": "text/html"})
    return response


def test_error_body_with_status_200_is_retried(make_project, capsys):
    builder = make_project(
        project=RETRY, request={"response_rules": [{"body_key": "error", "action": "retry"}]}
    )
    builder.http.get.side_effect = [reply({"error": "busy"}), page([{"id": 1}])]
    builder.run("full")
    assert stored(builder) == [{"id": 1}]
    assert "Response rules applied: retry=1" in capsys.readouterr().out


def test_error_body_that_persists_fails_the_run(make_project):
    builder = make_project(
        project=RETRY, request={"response_rules": [{"body_key": "error", "action": "retry"}]}
    )
    builder.http.get.return_value = reply({"error": "quota exceeded"})
    with pytest.raises(RuntimeError, match="response rule: retry"):
        builder.run("full")
    assert builder.http.get.call_count == 3
    assert not builder._load_state()


def test_accepted_status_is_processed(make_project):
    builder = make_project(request={"response_rules": [{"status": 404, "action": "accept"}]})
    builder.http.get.return_value = reply({"items": [], "total": 0}, 404)
    builder.run("full")
    assert builder._load_state()["records_processed"] == 0


def test_fail_rule_stops_without_retrying(make_project):
    builder = make_project(
        project=RETRY,
        request={"response_rules": [{"content_type": "text/html", "action": "fail"}]},
    )
    builder.http.get.return_value = html(503)
    with pytest.raises(RequestFailed, match="fail response rule"):
        builder._request(builder.start_url)
    assert builder.http.get.call_count == 1


def test_missing_rule_records_followed_object(make_project):
    builder = make_project(
        follow=FOLLOW,
        request={
            "response_rules": [{"body_key": "deleted", "body_value": True, "action": "missing"}]
        },
    )
    serve(builder, [{"id": 1}, {"id": 2}])
    builder.run("full")

    def detail(url, **kwargs):
        key = kwargs["params"]["id"]
        return reply({"id": key, "deleted": True} if key == 2 else {"id": key})

    builder.http.get.side_effect = detail
    builder.follow("full")
    missing = builder.details_storage_file[: -len(".zip")] + ".missing.json"
    with open(missing, encoding="utf8") as handle:
        assert json.load(handle) == [{"key": 2, "page": 1, "status": 200}]


def test_configured_404_retries_are_kept(make_project):
    builder = make_project(project=RETRY, error_handling={"retry_on_errors": [404]})
    builder.http.get.side_effect = [reply({}, 404), page([{"id": 1}])]
    builder.run("full")
    assert builder.http.get.call_count == 2


def test_rate_limit_reset_timestamp_sets_the_wait(make_project, monkeypatch):
    waits = []
    monkeypatch.setattr("apibackuper.cmds.project.time.sleep", waits.append)
    builder = make_project(
        project=RETRY, request={"retry": {"wait_headers": ["X-RateLimit-Reset", "Retry-After"]}}
    )
    limited = reply({}, 429)
    limited.headers = {"X-RateLimit-Reset": str(int(time.time()) + 30)}
    builder.http.get.side_effect = [limited, page([{"id": 1}])]
    builder.run("full")
    assert 28 <= waits[0] <= 31


def test_wait_longer_than_max_wait_fails(make_project):
    builder = make_project(project=RETRY, request={"retry": {"max_wait": 300}})
    limited = reply({}, 429)
    limited.headers = {"Retry-After": "3600"}
    builder.http.get.return_value = limited
    with pytest.raises(RequestFailed, match="max_wait"):
        builder._request(builder.start_url)
    assert builder.http.get.call_count == 1


def test_header_wait_formats():
    response = reply({})
    response.headers = {"Retry-After": "Wed, 21 Oct 2015 07:28:00 GMT"}
    assert header_wait(response, ["Retry-After"]) == 0
    response.headers = {"RateLimit-Reset": "15"}
    assert header_wait(response, ["Retry-After", "RateLimit-Reset"]) == 15
    assert header_wait(response, ["X-Other"]) is None


def test_rule_validation(make_project):
    errors = validate_rules(
        [
            {"action": "retry"},
            {"status": "6xx", "action": "accept"},
            {"body_value": 1, "status": 200, "action": "ignore"},
        ]
    )
    assert len(errors) == 4
    builder = make_project(request={"response_rules": [{"status": "5xx"}]})
    valid, count, _ = builder.validate_config()
    assert not valid and count >= 1
