"""Execute the actual documentation snippets against the local demo API."""

import json
import os
import runpy
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_quickstart_and_python_api(tmp_path):
    """Use real HTTP and CLI processes, then verify the documented output."""
    from scripts.validate_examples import markdown_blocks

    server = runpy.run_path(str(ROOT / "examples/local-demo/server.py"))["create_server"](0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    demo = tmp_path / "demo"
    shutil.copytree(ROOT / "examples/local-demo", demo)
    config_path = demo / "apibackuper.yaml"
    config = config_path.read_text()
    quickstart = ROOT / "docs/docs/getting-started/quick-start.md"
    blocks = list(markdown_blocks(quickstart))
    documented_config = next(body for language, meta, body in blocks if language == "yaml")
    assert yaml.safe_load(documented_config) == yaml.safe_load(config)
    config_path.write_text(config.replace(":8765/", f":{server.server_port}/"))
    env = {**os.environ, "PYTHONPATH": str(ROOT), "NO_PROXY": "127.0.0.1"}
    try:
        count = 0
        for page, cwd in [
            (quickstart, demo),
            (ROOT / "docs/docs/development/python-api.md", tmp_path),
        ]:
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
        assert count >= 8, "The walkthrough must exercise validation, run, export and Python API"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
