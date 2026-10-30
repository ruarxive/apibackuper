"""Agent-facing CLI: pagination probing, init, sample runs and --json output."""

import json
import logging
import runpy
import threading
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from apibackuper.cmds.probe import probe_pagination, record_fields
from apibackuper.cmds.project import ProjectBuilder
from apibackuper.cmds.utils import progress_disable, remove_query_keys, set_progress
from apibackuper.core import app

ROOT = Path(__file__).resolve().parents[1]
RECORDS = [{"id": number} for number in range(1, 8)]


def fake_api(page_param="page", size_param="per_page", offset_param=None, default=2, cap=None):
    """Return a fetch function serving RECORDS like an API with these parameter names."""
    calls = []

    def fetch(extra):
        calls.append(dict(extra))
        size = int(extra.get(size_param, default)) if size_param else default
        size = min(size, cap) if cap else size
        if offset_param and offset_param in extra:
            start = int(extra[offset_param])
        elif page_param and page_param in extra:
            start = (int(extra[page_param]) - 1) * size
        else:
            start = 0
        return RECORDS[start : start + size]

    fetch.calls = calls
    return fetch


def test_probe_finds_page_and_size_parameters():
    result = probe_pagination(fake_api(), RECORDS[:2], total=7)
    assert result["iterate_by"] == "page"
    assert result["page_number_param"] == "page"
    assert result["page_size_param"] == "per_page"
    assert result["page_size_limit"] == 100
    assert result["warnings"] == []


def test_probe_reports_capped_page_size():
    capped = probe_pagination(fake_api(cap=3), RECORDS[:2], total=7)
    assert capped["page_size_limit"] == 3
    unknown_total = probe_pagination(fake_api(cap=3), RECORDS[:2])
    assert unknown_total["page_size_limit"] == 3
    assert "caps the page size" in unknown_total["warnings"][0]


def test_probe_finds_offset_parameters():
    fetch = fake_api(page_param=None, size_param="limit", offset_param="offset")
    result = probe_pagination(fetch, RECORDS[:2], total=7)
    assert result["iterate_by"] == "skip"
    assert result["count_skip_param"] == "offset"
    assert result["page_size_param"] == "limit"


def test_probe_without_working_parameter_warns():
    result = probe_pagination(lambda extra: RECORDS[:2], RECORDS[:2], total=7)
    assert "iterate_by" not in result
    assert result["page_size_limit"] == 2
    assert "set params.page_number_param" in result["warnings"][0]
    failing = probe_pagination(lambda extra: None, RECORDS[:2])
    assert "iterate_by" not in failing


def test_probe_skips_single_page_datasets():
    fetch = fake_api()
    result = probe_pagination(fetch, RECORDS[:2], total=2)
    assert fetch.calls == []
    assert "fit on the first page" in result["warnings"][0]


def test_probe_tries_names_from_the_request_first_and_respects_modes():
    fetch = fake_api(page_param="pageNo")
    result = probe_pagination(fetch, RECORDS[:2], preferred=["q", "pageNo"])
    assert fetch.calls[0] == {"pageNo": 2}
    assert result["page_number_param"] == "pageNo"
    offset_only = fake_api(page_param=None, offset_param="skip")
    probe_pagination(offset_only, RECORDS[:2], modes=("skip",))
    assert all("page" not in call for call in offset_only.calls)


def test_record_fields_and_query_cleanup():
    assert record_fields([{"b": 1, "a": 2}, {"c": 3}, "text"]) == ["a", "b", "c"]
    assert remove_query_keys("https://x/items?page=1&q=a", ["page"]) == "https://x/items?q=a"
    raw = "https://x/oz?b[Date]=01.01.2020%%20-%%20"
    assert remove_query_keys(raw, ["page"]) == raw


def test_progress_bars_follow_the_terminal_unless_turned_off():
    try:
        set_progress(True)
        assert progress_disable() is None
        assert progress_disable(True) is True
        set_progress(False)
        assert progress_disable() is True
    finally:
        set_progress(True)


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Run in a temporary directory and restore the root logger afterwards."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    monkeypatch.chdir(tmp_path)
    yield tmp_path
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.fixture
def demo_url(monkeypatch):
    """Serve the local demo API (five records, page/per_page) on a free port."""
    server = runpy.run_path(str(ROOT / "examples/local-demo/server.py"))["create_server"](0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    yield f"http://127.0.0.1:{server.server_port}/items"
    server.shutdown()
    server.server_close()


def write_config(path, url, **params):
    config = {
        "settings": {"name": "demo"},
        "project": {"url": url, "http_mode": "GET", "default_delay": 0},
        "params": {"page_size_limit": 2, **params},
        "data": {"data_key": "items", "total_number_key": "total"},
        "storage": {"storage_type": "zip"},
    }
    (path / "apibackuper.yaml").write_text(yaml.safe_dump(config), encoding="utf8")


def invoke(*args):
    return CliRunner().invoke(app, list(args))


def test_missing_pagination_parameter_is_a_warning(project_dir):
    write_config(project_dir, "https://api.example.com/items")
    builder = ProjectBuilder(str(project_dir))
    try:
        report = builder.validation_report()
    finally:
        builder.http.close()
    assert report["valid"]
    (warning,) = report["warnings"]
    assert warning["path"] == "params.page_number_param"
    assert "only the first page" in warning["message"]
    assert "hint" in warning

    result = invoke("validate-config", "--strict", "--json")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["warnings"][0]["path"] == "params.page_number_param"
    assert invoke("validate-config", "--json").exit_code == 0


def test_dry_run_plan_lists_warnings_as_json_only(project_dir):
    write_config(project_dir, "https://api.example.com/items")
    result = invoke("run", "full", "--dry-run")
    assert result.exit_code == 0, result.output
    plan = json.loads(result.stdout)
    assert "only the first page" in plan["warnings"][0]


def test_json_mode_wraps_results_and_errors(project_dir):
    write_config(project_dir, "https://api.example.com/items", page_number_param="page")
    ok = invoke("--json", "validate-config")
    assert ok.exit_code == 0
    payload = json.loads(ok.stdout)
    assert payload["ok"] is True and payload["command"] == "validate-config"
    assert payload["result"]["valid"] is True

    missing = invoke("--json", "run", "full", "-p", str(project_dir / "absent"))
    assert missing.exit_code == 1
    error = json.loads(missing.stdout)
    assert error["ok"] is False
    assert error["error"]["code"] == "config_not_found"
    assert error["error"]["hints"]

    usage = invoke("--json", "run", "full", "--max-pages", "0")
    assert usage.exit_code == 2
    assert json.loads(usage.stdout)["error"]["code"] == "usage_error"


def test_schema_command_prints_the_bundled_schema(project_dir):
    result = invoke("schema")
    assert result.exit_code == 0
    assert "page_size_limit" in json.loads(result.stdout)["properties"]["params"]["properties"]


def test_detect_probes_pagination_and_cleans_the_url(project_dir, demo_url, monkeypatch):
    monkeypatch.setattr("apibackuper.cmds.project.time.sleep", lambda seconds: None)
    result = invoke("detect", "--url", f"{demo_url}?page=1")
    assert result.exit_code == 0, result.output
    config = yaml.safe_load(result.stdout)
    assert config["project"]["url"] == demo_url
    assert config["project"]["iterate_by"] == "page"
    assert config["params"]["page_number_param"] == "page"
    assert config["params"]["page_size_param"] == "per_page"


def test_sample_run_previews_without_touching_the_project(project_dir, demo_url):
    write_config(project_dir, demo_url, page_number_param="page", page_size_param="per_page")
    result = invoke("--json", "run", "full", "--max-pages", "2")
    assert result.exit_code == 0, result.output
    sample = json.loads(result.stdout)["result"]
    assert (sample["pages"], sample["records"], sample["total_reported"]) == (2, 4, 5)
    assert sample["more_pages"] is True
    assert sample["fields"] == ["id", "title", "updated_at"]
    assert len(sample["preview"]) == 3
    assert sorted(p.name for p in project_dir.iterdir()) == ["apibackuper.log", "apibackuper.yaml"]


def test_sample_run_fails_when_the_api_ignores_the_parameter(project_dir, demo_url):
    write_config(project_dir, demo_url, page_number_param="wrong")
    result = invoke("--json", "run", "full", "--max-pages", "2")
    assert result.exit_code == 1
    assert json.loads(result.stdout)["error"]["code"] == "pagination_ignored"


def test_init_writes_a_working_project(project_dir, demo_url, monkeypatch):
    monkeypatch.setattr("apibackuper.cmds.project.time.sleep", lambda seconds: None)
    result = invoke("--json", "init", "catalog", "--url", f"{demo_url}?per_page=2&lang=en")
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)["result"]
    assert report["valid"] is True
    assert report["detected"]["page_number_param"] == "page"
    assert report["sample_record"] == {"id": 1, "title": "Item 1", "updated_at": "2026-01-01"}
    assert report["next_steps"][-1] == "apibackuper export catalog.jsonl"
    project = project_dir / "catalog"
    config = yaml.safe_load((project / "apibackuper.yaml").read_text(encoding="utf8"))
    assert config["project"]["url"] == demo_url
    assert json.loads((project / "params.json").read_text(encoding="utf8")) == {"lang": "en"}

    assert invoke("run", "full", "-p", str(project)).exit_code == 0
    assert invoke("export", "items.jsonl", "-p", str(project)).exit_code == 0
    assert len((project_dir / "items.jsonl").read_text(encoding="utf8").splitlines()) == 5

    again = invoke("--json", "init", "catalog", "--url", demo_url)
    assert json.loads(again.stdout)["error"]["code"] == "already_exists"


def test_init_keeps_secrets_as_placeholders(project_dir, monkeypatch):
    monkeypatch.delenv("APIBACKUPER_TEST_TOKEN", raising=False)
    result = invoke(
        "init",
        "secure",
        "--url",
        "https://api.example.com/items",
        "--auth",
        "bearer",
        "--auth-env",
        "APIBACKUPER_TEST_TOKEN",
        "-H",
        "Accept: application/json",
    )
    assert result.exit_code == 0, result.output
    report = json.loads(result.stdout)
    assert "APIBACKUPER_TEST_TOKEN is not set" in report["warnings"][0]
    assert report["next_steps"][0] == "export APIBACKUPER_TEST_TOKEN=..."
    config = yaml.safe_load((project_dir / "secure/apibackuper.yaml").read_text(encoding="utf8"))
    assert config["auth"] == {"type": "bearer", "token": "${APIBACKUPER_TEST_TOKEN}"}
    headers = json.loads((project_dir / "secure/headers.json").read_text(encoding="utf8"))
    assert headers == {"Accept": "application/json"}
