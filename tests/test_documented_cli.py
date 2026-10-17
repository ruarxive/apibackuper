"""Regression proof for the logging and filtering contracts in the docs."""

import logging

import pytest
import yaml
from typer.testing import CliRunner

from apibackuper.cmds.project import ProjectBuilder
from apibackuper.core import app


@pytest.fixture
def documented_project(tmp_path, monkeypatch):
    """Keep real project logging isolated from pytest's handlers and files."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    monkeypatch.chdir(tmp_path)
    config = {
        "settings": {"name": "documented"},
        "project": {"url": "http://127.0.0.1:8765/items", "http_mode": "GET"},
        "params": {"page_size_limit": 2, "page_number_param": "page"},
        "data": {"data_key": "items", "total_number_key": "total"},
        "storage": {"storage_type": "zip"},
        "logging": {"level": "ERROR"},
    }
    (tmp_path / "apibackuper.yaml").write_text(yaml.safe_dump(config), encoding="utf8")
    yield tmp_path
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers[:] = handlers
    root.setLevel(level)


@pytest.mark.parametrize(
    "args,method,result",
    [
        (["run", "full"], "run", None),
        (["update"], "update", None),
        (["export", "out.jsonl"], "export", None),
        (["detect"], "detect", {}),
        (["detect", "--url", "http://127.0.0.1:8765/items"], "detect", {}),
    ],
)
def test_verbose_survives_real_project_initialization(
    documented_project, monkeypatch, args, method, result
):
    def emit(self, *args, **kwargs):
        logging.info("documented-console-message")
        return result

    monkeypatch.setattr(ProjectBuilder, method, emit)
    invocation = CliRunner().invoke(app, [*args, "--verbose"])
    assert invocation.exit_code == 0, invocation.output
    assert "documented-console-message" in invocation.output
    assert "documented-console-message" in (documented_project / "apibackuper.log").read_text()


def test_configured_log_level_is_respected(documented_project):
    project = ProjectBuilder(str(documented_project))
    try:
        logging.warning("hidden-warning")
        logging.error("visible-error")
        log = (documented_project / "apibackuper.log").read_text()
        assert "hidden-warning" not in log
        assert "visible-error" in log
    finally:
        project.http.close()


@pytest.mark.parametrize("expression", ["id = 2", "id > 1 AND id < 3"])
def test_invalid_export_filter_fails_without_replacing_output(documented_project, expression):
    output = documented_project / "out.jsonl"
    output.write_text("previous export\n", encoding="utf8")
    result = CliRunner().invoke(app, ["export", str(output), "--where", expression])
    assert result.exit_code == 1, result.output
    assert "Invalid --where" in result.output
    assert output.read_text() == "previous export\n"
