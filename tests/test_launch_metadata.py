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


@pytest.mark.parametrize("page", ["contribute", "corrections", "data", "disclaimer", "methodology"])
def test_support_shell_separates_platform_and_evidence(page):
    soup = BeautifulSoup((ROOT / f"site/{page}.html").read_text(), "html.parser")
    assert soup.select_one('.status-strip').get_text() == (
        "THE BENGAL FOODPATH · SOURCE-CONSCIOUS DISCOVERY"
    )
    assert soup.select_one('.policy-nav a').get_text() == "The Bengal FoodPath"
    assert "Inclusion is not a finding of wrongdoing" in soup.select_one('main').get_text()
    for link in soup.select('a'):
        if "Return to Food Safety Evidence" in link.get_text():
            assert link['href'] == "index.html?module=safety"


def test_generated_policies_have_neutral_shell_and_scoped_evidence_context(project):
    build(project)
    for name in POLICIES:
        soup = BeautifulSoup(
            (project / f"site/policies/{name.lower()}.html").read_text(), "html.parser"
        )
        assert "research tracker" not in soup.select_one('.status-strip').get_text()
        context = soup.select_one('[data-evidence-context]').get_text()
        assert "Food Safety Evidence (West Bengal)" in context
        assert "not a finding of wrongdoing" in context


def test_about_contribution_and_correction_context_is_current():
    about = (ROOT / "site/methodology.html").read_text()
    assert about.index("Puja FoodPath</h2>") < about.index('data-evidence-context')
    for region in ["California", "London", "Toronto/GTA", "Melbourne"]:
        assert region in about
    for page in ["contribute", "corrections"]:
        html = (ROOT / f"site/{page}.html").read_text()
        assert "Suggest a Puja" in html
        assert "when the maintainer makes the repository public" not in html
        assert "form remains hidden" not in html


def test_internal_html_links_and_assets_exist():
    from urllib.parse import unquote, urlsplit

    root = ROOT / "site"
    for path in root.rglob("*.html"):
        soup = BeautifulSoup(path.read_text(), "html.parser")
        for tag in soup.select('a[href], link[href], script[src], img[src]'):
            url = urlsplit(tag.get('href') or tag.get('src'))
            if url.scheme or url.netloc or not url.path:
                continue
            target = (
                root / unquote(url.path.lstrip('/')) if url.path.startswith('/')
                else path.parent / unquote(url.path)
            )
            assert (target.exists() or target.with_suffix('.html').exists()
                    or (target / 'index.html').exists()), (path, url.path)
