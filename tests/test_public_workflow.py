from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_refresh_is_two_hour_bounded_and_has_no_push_loop():
    workflow = yaml.load(
        (ROOT / ".github/workflows/update-data.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert workflow["name"] == "Refresh Food Safety Data"
    assert set(workflow["on"]) == {"workflow_dispatch", "schedule"}
    assert workflow["on"]["schedule"][0]["cron"] == "17 */2 * * *"
    job = workflow["jobs"]["candidates"]
    assert job["env"]["AUTO_PUBLISH"] == "true"
    assert job["permissions"] == {"contents": "write"}
    steps = "\n".join(step.get("run", "") for step in job["steps"])
    assert "--max-articles 6" in steps
    assert "verify_public_output.py" in steps
    assert "git diff --cached --quiet" in steps
    assert "git add ." not in steps
    assert "upload-artifact" not in str(workflow)


def test_canonical_urls_and_readme_assets_exist():
    import re

    text = (ROOT / "README.md").read_text()
    for path in re.findall(r"!\[[^]]*\]\((docs/assets/[^)]+)\)", text):
        assert (ROOT / path).is_file()
    html = (ROOT / "site/index.html").read_text()
    assert "https://foodsafety.nemoneek.com/" in html
    assert 'property="og:image"' in html
    assert (ROOT / "site/assets/social-preview.png").is_file()
    config = (ROOT / "wrangler.jsonc").read_text()
    assert '"directory": "./site"' in config


def test_private_local_artifacts_are_ignored():
    text = (ROOT / ".gitignore").read_text()
    for path in ["data/history/", "data/pending.json", "data/rejected.json", ".cache/", ".env"]:
        assert path in text
