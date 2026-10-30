"""The published llms-full.txt must match the documentation pages it is built from."""

from pathlib import Path

from scripts import build_llms_full

ROOT = Path(__file__).resolve().parents[1]


def test_listed_pages_exist():
    for page in build_llms_full.PAGES:
        assert (ROOT / "docs/docs" / page).is_file(), page


def test_llms_full_is_current():
    message = "docs/static/llms-full.txt is stale; run python -m scripts.build_llms_full"
    assert build_llms_full.main(["--check"]) == 0, message


def test_site_links_are_absolute():
    text = build_llms_full.render(ROOT)
    assert "](/" not in text
    assert "Source: https://ruarxive.org/apibackuper/configuration/pagination" in text
