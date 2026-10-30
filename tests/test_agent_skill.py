"""Keep the bundled agent skill and plugin manifests in sync with the CLI."""

import json
import re
import shlex
from pathlib import Path

import pytest
import typer
import yaml

from apibackuper.core import app

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
SKILL_FILES = sorted(SKILLS.rglob("*.md"))


def cited_commands(text):
    """Yield apibackuper command lines from shell blocks and inline code."""
    for block in re.finditer(r"^\s*```(?:bash|sh)\n(.*?)^\s*```", text, re.MULTILINE | re.DOTALL):
        for line in block.group(1).splitlines():
            for part in re.split(r"&&|\|", line):
                part = part.strip()
                if part.startswith("apibackuper "):
                    yield part
    for match in re.finditer(r"`(apibackuper [^`]+)`", text):
        yield match.group(1)


def option_names(command):
    """Return the option names a Click command accepts, including --help."""
    names = {opt for param in command.params for opt in param.opts if opt.startswith("-")}
    return names | {"--help"}


def cli_options():
    """Map each CLI command name, and None for the top level, to its option names."""
    group = typer.main.get_command(app)
    options = {name: option_names(command) for name, command in group.commands.items()}
    options[None] = option_names(group)
    return options


def test_skill_files_exist():
    assert (SKILLS / "apibackuper" / "SKILL.md").is_file()


def test_skill_frontmatter_follows_agent_skills_format():
    text = (SKILLS / "apibackuper" / "SKILL.md").read_text(encoding="utf8")
    match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    assert match, "SKILL.md must start with YAML frontmatter"
    meta = yaml.safe_load(match.group(1))
    assert meta["name"] == "apibackuper"
    assert re.fullmatch(r"[a-z0-9-]{1,64}", meta["name"])
    assert 0 < len(meta["description"]) <= 1024


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda path: str(path.relative_to(SKILLS)))
def test_skill_cites_only_existing_commands_and_options(path):
    options = cli_options()
    text = path.read_text(encoding="utf8")
    for line in cited_commands(text):
        args = shlex.split(line)[1:]
        assert args, f"{path.name}: bare command {line!r}"
        command = None if args[0].startswith("-") else args.pop(0)
        assert command in options, f"{path.name}: unknown command in {line!r}"
        for arg in args:
            if arg.startswith("-"):
                name = arg.split("=", 1)[0]
                assert name in options[command], f"{path.name}: unknown option {name} in {line!r}"


@pytest.mark.parametrize("path", SKILL_FILES, ids=lambda path: str(path.relative_to(SKILLS)))
def test_skill_relative_links_resolve(path):
    text = path.read_text(encoding="utf8")
    for target in re.findall(r"\]\(([^)#]+)\)", text):
        if "://" not in target:
            assert (path.parent / target).exists(), f"{path.name}: broken link {target}"


def test_plugin_manifests_agree_with_package():
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf8"))
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text(encoding="utf8"))
    version = re.search(
        r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf8"), re.M
    ).group(1)
    (entry,) = marketplace["plugins"]
    assert entry["name"] == plugin["name"] == "apibackuper"
    assert entry["source"] == "./"
    assert entry["version"] == plugin["version"] == version
