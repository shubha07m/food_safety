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
        assert " · FoodPath</title>" in path.read_text()


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
        "FOODPATH · SOURCE-CONSCIOUS DISCOVERY"
    )
    assert soup.select_one('.policy-nav a').get_text() == "FoodPath"
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


def test_final_public_foodpath_brand():
    old_brand = "bengal" + " foodpath"
    paths = list(ROOT.glob('*.md')) + list((ROOT / 'docs').rglob('*.md'))
    paths += list((ROOT / 'docs/assets').glob('*.svg'))
    paths += [p for p in (ROOT / 'site').rglob('*') if p.suffix in {'.html', '.mjs', '.js', '.svg'}]
    for path in paths:
        if path.name == 'AGENTS.md':  # local operator guide is not a public asset
            continue
        assert old_brand not in path.read_text().lower(), path
    html = BeautifulSoup((ROOT / 'site/index.html').read_text(), 'html.parser')
    assert html.title.get_text() == 'FoodPath · Puja pandals and nearby food'
    assert html.select_one('.identity')['aria-label'] == 'FoodPath home'
    assert html.select_one('meta[property="og:title"]')['content'] == 'FoodPath · Puja FoodPath'
    assert html.select_one('footer strong').get_text() == 'FOODPATH'
    assert html.select_one('.module-title').get_text() == 'West Bengal Food Safety Evidence Tracker'


def test_readme_final_brand_and_owner_command():
    readme = (ROOT / 'README.md').read_text()
    assert readme.startswith('# FoodPath\n')
    assert 'python -m food_safety.cli puja review' in readme
    assert '**West Bengal only**' in readme
    assert 'Other festival families are not\nimplemented.' in readme
    assert 'The local review app syncs responses' in (ROOT / 'PRIVACY.md').read_text()


def test_social_preview_source_matches_final_brand():
    svg = (ROOT / 'site/assets/social-preview.svg').read_text()
    assert '>FoodPath</text>' in svg
    assert 'The Bengal' not in svg
    assert 'Food Safety Evidence remains a separate West Bengal research module.' in svg


def test_puja_and_food_safety_corrections_have_separate_intake_contexts():
    soup = BeautifulSoup((ROOT / 'site/corrections.html').read_text(), 'html.parser')
    puja = soup.select_one('#puja-corrections')
    assert 'Google Form' in puja.get_text()
    assert 'no GitHub account needed' in puja.get_text()
    assert puja.select_one('#puja-correction-action')
    assert not puja.select_one('#correction-link')
    evidence = soup.select_one('[data-evidence-context]')
    assert 'West Bengal' in evidence.get_text()
    assert 'Inclusion is not a finding of wrongdoing' in evidence.get_text()
    assert evidence.select_one('#correction-link')
    assert evidence.select_one('#source-link')
    assert 'record a neutral revision or dispute status' in evidence.get_text()
    assert 'private GitHub' not in (ROOT / 'CORRECTIONS.md').read_text()
    policy = BeautifulSoup((ROOT / 'site/policies/corrections.html').read_text(), 'html.parser')
    assert policy.select_one('a[href="https://foodpath.nemoneek.com/corrections"]')
