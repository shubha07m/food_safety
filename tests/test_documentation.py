"""Current public documentation points to real local files and keeps module scope clear."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = [
    ROOT / name
    for name in (
        "README.md",
        "METHODOLOGY.md",
        "CONTRIBUTING.md",
        "DISCLAIMER.md",
        "PRIVACY.md",
        "SECURITY.md",
    )
] + list((ROOT / "docs").rglob("*.md"))


def test_public_document_links_and_local_path_boundary():
    for path in PUBLIC:
        text = path.read_text()
        assert "/" + "Users/" not in text, path.name
        assert not re.search(r"AIza[0-9A-Za-z_-]{30,}", text), path.name
        for destination in re.findall(r"\]\(([^)]+)\)", text):
            destination = destination.split("#")[0].split(' "')[0]
            if not destination or "://" in destination or destination.startswith("mailto:"):
                continue
            assert (path.parent / destination).is_file(), (path.name, destination)


def test_readme_separates_regions_rights_and_runtime_configuration():
    text = " ".join((ROOT / "README.md").read_text().split())
    assert "Kolkata region" in text and "California" in text
    assert "West Bengal only" in text
    assert "ODbL-1.0" in text
    assert "not relicensed as MIT" in text
    assert "coordinate pin is not a claim of exact Google business identity" in text
    assert "ordinary local static server shows the live-map fallback" in text
