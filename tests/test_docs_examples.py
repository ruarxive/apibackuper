"""Execute the actual documentation snippets against the local demo API."""

import json
import os
import runpy
import shlex
import shutil
import subprocess
import sys
import threading
from itertools import permutations
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("walkthrough", ["quick-start", "rest-api-backup", "post-api-backup"])
def test_local_walkthroughs(tmp_path, walkthrough):
    """Use real HTTP and CLI processes, then verify the documented output."""
    from scripts.validate_examples import markdown_blocks

    demo = tmp_path / "demo"
    section = "getting-started" if walkthrough == "quick-start" else "use-cases"
    page = ROOT / f"docs/docs/{section}/{walkthrough}.md"
    blocks = list(markdown_blocks(page))
    documented_config = next(body for language, meta, body in blocks if language == "yaml")
    if walkthrough == "quick-start":
        shutil.copytree(ROOT / "examples/local-demo", demo)
        shipped_config = (demo / "apibackuper.yaml").read_text()
        assert yaml.safe_load(documented_config) == yaml.safe_load(shipped_config)
    else:
        demo.mkdir()
    for language, meta, body in blocks:
        if language == "json" and "request-body" in meta.split():
            (demo / "params.json").write_text(body, encoding="utf8")
    pages = [(page, demo)]
    if walkthrough == "quick-start":
        pages.extend(
            [
                (ROOT / "docs/docs/use-cases/export-and-storage.md", demo),
                (ROOT / "docs/docs/development/python-api.md", tmp_path),
            ]
        )

    server = runpy.run_path(str(ROOT / "examples/local-demo/server.py"))["create_server"](0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    env = {**os.environ, "PYTHONPATH": str(ROOT), "NO_PROXY": "127.0.0.1"}
    try:
        (demo / "apibackuper.yaml").write_text(
            documented_config.replace(":8765/", f":{server.server_port}/"), encoding="utf8"
        )
        count = 0
        for page, cwd in pages:
            for language, meta, body in markdown_blocks(page):
                if "doc-test" not in meta.split():
                    continue
                if language == "python":
                    commands = [[sys.executable, "-c", body]]
                else:
                    commands = []
                    for line in body.splitlines():
                        if not line.strip() or line.lstrip().startswith("#"):
                            continue
                        args = shlex.split(line)
                        assert args[0] == "apibackuper", f"Unsupported docs command: {line}"
                        commands.append([sys.executable, "-m", "apibackuper", *args[1:]])
                for command in commands:
                    result = subprocess.run(
                        command, cwd=cwd, env=env, capture_output=True, text=True, timeout=30
                    )
                    assert result.returncode == 0, result.stdout + result.stderr
                    if command[1:4] == ["-m", "apibackuper", "info"]:
                        report = json.loads(result.stdout)
                        assert report["run"]["records_processed"] == 5
                        assert report["statistics"]["storage"]["total_records"] == 5
                    count += 1
        assert count >= 7, "Each walkthrough must execute its CLI commands and output checks"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("conflicting_latest", [False, True])
def test_documented_current_view(tmp_path, conflicting_latest):
    """History order and older ties must not silently select a stale version."""
    from scripts.validate_examples import markdown_blocks

    page = ROOT / "docs/docs/use-cases/export-and-storage.md"
    code = next(
        body for language, meta, body in markdown_blocks(page) if "history-view" in meta.split()
    )
    history = [
        {"id": 2, "metadata_modified": "2026-01-01", "title": "Old"},
        {"id": 2, "metadata_modified": "2026-01-01", "title": "Old conflict"},
        {"id": 2, "metadata_modified": "2026-01-02", "title": "Current"},
    ]
    if conflicting_latest:
        history[1]["metadata_modified"] = "2026-01-02"
    for ordered in permutations(history):
        (tmp_path / "history.jsonl").write_text(
            "\n".join(json.dumps(row) for row in ordered), encoding="utf8"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        output = tmp_path / "current.jsonl"
        if conflicting_latest:
            assert result.returncode != 0
            assert "Conflicting latest versions" in result.stderr
            assert not output.exists()
        else:
            assert result.returncode == 0, result.stdout + result.stderr
            assert [json.loads(line) for line in output.read_text().splitlines()] == [history[2]]
