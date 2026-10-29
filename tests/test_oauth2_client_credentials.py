"""OAuth2 client credentials (openspec add-oauth2-client-credentials)."""

import threading
import time
from unittest.mock import Mock

import pytest

from apibackuper.auth import AuthHandler
from apibackuper.cmds.config_loader import YAMLConfigParser
from tests import test_backup_workflow as workflow

# Reuse the workflow fixture and helpers: mocked HTTP session, real storage.
make_project = workflow.make_project
reply, serve = workflow.reply, workflow.serve

CLIENT = {
    "type": "oauth2",
    "grant_type": "client_credentials",
    "auth_url": "https://auth.example.test/token",
    "client_id": "backup-client",
    "client_secret": "client-secret-value",
    "scope": "read",
}
RECORDS = [{"id": n} for n in range(5)]


def tokens(builder, *responses):
    builder.http.post.side_effect = list(responses)


def bearer(call):
    return call.kwargs["headers"]["Authorization"]


def test_token_fetched_before_first_request_with_basic_client_auth(make_project):
    builder = make_project(auth=CLIENT)
    tokens(builder, reply({"access_token": "t1", "expires_in": 3600}))
    serve(builder, RECORDS)
    builder.run("full")
    assert builder.http.mock_calls[0][0] == "post"
    token_call = builder.http.post.call_args
    assert token_call.kwargs["auth"] == ("backup-client", "client-secret-value")
    assert token_call.kwargs["data"] == {"grant_type": "client_credentials", "scope": "read"}
    assert {bearer(call) for call in builder.http.get.call_args_list} == {"Bearer t1"}
    assert builder.http.post.call_count == 1


def test_client_secret_post_sends_credentials_in_body(make_project):
    builder = make_project(auth=dict(CLIENT, client_auth_method="client_secret_post"))
    tokens(builder, reply({"access_token": "t1"}))
    serve(builder, RECORDS[:1])
    builder.run("full")
    token_call = builder.http.post.call_args
    assert "auth" not in token_call.kwargs
    assert token_call.kwargs["data"]["client_id"] == "backup-client"
    assert token_call.kwargs["data"]["client_secret"] == "client-secret-value"


def test_token_renewed_before_expiry(make_project, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr("apibackuper.auth.time.monotonic", lambda: clock[0])
    builder = make_project(auth=CLIENT)
    tokens(
        builder,
        reply({"access_token": "t1", "expires_in": 120}),
        reply({"access_token": "t2", "expires_in": 120}),
    )

    def get(url, **kwargs):
        clock[0] += 70  # each page takes 70 seconds
        page = int(kwargs["params"]["page"])
        return reply({"items": RECORDS[(page - 1) * 2 : page * 2], "total": len(RECORDS)})

    builder.http.get.side_effect = get
    builder.run("full")
    assert [bearer(call) for call in builder.http.get.call_args_list] == [
        "Bearer t1",
        "Bearer t2",
        "Bearer t2",
    ]


def test_rejected_token_is_replaced_and_request_retried(make_project):
    builder = make_project(auth=CLIENT)
    tokens(builder, reply({"access_token": "t1"}), reply({"access_token": "t2"}))
    responses = [reply({}, 401), reply({"items": [{"id": 1}], "total": 1})]
    sent = []

    def get(url, **kwargs):
        # Record the header at call time: the retry reuses the headers dict.
        sent.append(kwargs["headers"]["Authorization"])
        return responses.pop(0)

    builder.http.get.side_effect = get
    builder.run("full")
    assert sent == ["Bearer t1", "Bearer t2"]


def test_refresh_grant_authenticates_client_when_configured():
    handler = AuthHandler(
        YAMLConfigParser(
            {
                "auth": {
                    "type": "oauth2",
                    "token": "old",
                    "refresh_token": "refresh-value",
                    "auth_url": "https://auth.example.test/token",
                    "client_id": "backup-client",
                    "client_secret": "client-secret-value",
                }
            }
        )
    )
    session = Mock()
    session.post.return_value = reply({"access_token": "new"})
    assert handler.refresh_token_if_needed(session, failed_token="old")
    kwargs = session.post.call_args.kwargs
    assert kwargs["auth"] == ("backup-client", "client-secret-value")
    assert kwargs["data"] == {"grant_type": "refresh_token", "refresh_token": "refresh-value"}


def test_missing_client_secret_file_blocks_requests(make_project, tmp_path):
    settings = {k: v for k, v in CLIENT.items() if k != "client_secret"}
    builder = make_project(auth=dict(settings, client_secret_file=str(tmp_path / "absent")))
    valid, errors, _ = builder.validate_config()
    assert not valid
    with pytest.raises(ValueError, match="client_secret_file not found"):
        builder._request(builder.start_url)
    builder.http.post.assert_not_called()
    builder.http.get.assert_not_called()


def test_client_credentials_fields_are_validated(make_project):
    builder = make_project(auth={"type": "oauth2", "grant_type": "client_credentials"})
    valid, errors, _ = builder.validate_config()
    assert not valid and errors == 3


def test_parallel_requests_share_one_token_request():
    handler = AuthHandler(YAMLConfigParser({"auth": CLIENT}))
    session = Mock()

    def slow_token(url, **kwargs):
        time.sleep(0.05)
        return reply({"access_token": "shared"})

    session.post.side_effect = slow_token
    start = threading.Barrier(4)

    def worker():
        start.wait()
        handler.ensure_token(session)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert session.post.call_count == 1
    assert handler.get_headers() == {"Authorization": "Bearer shared"}


def test_token_endpoint_failure_hides_secrets(make_project, caplog):
    builder = make_project(auth=CLIENT)
    echoed = reply({"error": "invalid_client", "echo": "client_secret=client-secret-value"}, 400)
    builder.http.post.return_value = echoed
    with pytest.raises(RuntimeError) as failure:
        builder.run("full")
    assert "client-secret-value" not in str(failure.value)
    assert "client-secret-value" not in caplog.text
    builder.http.get.assert_not_called()
