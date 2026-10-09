import json
from pathlib import Path
from xml.etree import ElementTree

import pytest
from bs4 import BeautifulSoup

from food_safety.build import POLICIES, build
from food_safety.config import Settings

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://foodpath.nemoneek.com/"


def canonical(path):
    tags = BeautifulSoup(path.read_text(), "html.parser").select('link[rel="canonical"]')
    assert len(tags) == 1
    return tags[0]["href"]


def test_primary_origin_and_consolidated_static_app():
    assert Settings().site_url == ORIGIN
    assert canonical(ROOT / "site/index.html") == ORIGIN
    html = BeautifulSoup((ROOT / "site/index.html").read_text(), "html.parser")
    assert html.select_one('meta[property="og:url"]')["content"] == ORIGIN
    assert not html.select('link[rel="alternate"][hreflang]')
    assert "canonical" not in (ROOT / "site/app.js").read_text()
    assert json.loads((ROOT / "site/repository.json").read_text())["site_url"] == ORIGIN
    assert json.loads((ROOT / "site/repository.json").read_text())["puja_suggest_form_url"] == (
        "https://forms.gle/DfebWArXd7AFtH9d7"
    )


@pytest.mark.parametrize("page", ["contribute", "corrections", "data", "disclaimer", "methodology"])
def test_support_page_canonicals(page):
    assert canonical(ROOT / f"site/{page}.html") == ORIGIN + page


def test_build_generates_policy_canonicals(project):
    build(project)
    for name in POLICIES:
        path = project / f"site/policies/{name.lower()}.html"
        assert canonical(path) == ORIGIN + "policies/" + name.lower()
        assert " · The Bengal FoodPath</title>" in path.read_text()


def test_small_sitemap_and_robots():
    tree = ElementTree.fromstring((ROOT / "site/sitemap.xml").read_text())
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    assert [e.text for e in tree.findall("s:url/s:loc", ns)] == [ORIGIN]
    assert tree.findall("s:url/s:lastmod", ns) == []
    assert f"Sitemap: {ORIGIN}sitemap.xml" in (ROOT / "site/robots.txt").read_text()


def test_old_origin_absent_from_public_output_and_primary_defaults():
    for path in (ROOT / "site").rglob("*"):
        if path.suffix in {".html", ".js", ".mjs", ".json", ".xml", ".txt"}:
            assert "foodsafety.nemoneek.com" not in path.read_text(), path
    assert "foodsafety.nemoneek.com" not in (ROOT / "src/food_safety/config.py").read_text()
