"""Ensure the documentation gate catches invalid authored examples."""

import pytest

from scripts import validate_examples


@pytest.mark.parametrize(
    "block,expected",
    [
        ("```yaml\nrequest:\n  parallelism: 2\n```\n", 0),
        ("```yaml\nrequest:\n  parallellism: 2\n```\n", 1),
        ("```yaml\nparams:\n  page_size_limit: 0\n```\n", 1),
        ('```json\n{"id": }\n```\n', 1),
        ("```yaml config\nsettings:\n  name: missing-sections\n```\n", 1),
    ],
)
def test_documentation_gate_checks_fragments_and_complete_configs(
    tmp_path, monkeypatch, block, expected
):
    for name in [
        "README.md",
        "SECURITY.md",
        "docs/README.md",
        "docs/GITHUB_PAGES_SETUP.md",
        ".github/workflows/README.md",
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf8")
    (tmp_path / "README.md").write_text(block, encoding="utf8")
    monkeypatch.setattr(
        validate_examples, "__file__", str(tmp_path / "scripts/validate_examples.py")
    )
    assert validate_examples.main() == expected
