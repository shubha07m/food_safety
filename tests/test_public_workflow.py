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


def test_public_status_does_not_depend_on_private_queue_contents(project):
    import json

    from food_safety.build import build

    path = project / "data/status.json"
    status = json.loads(path.read_text())
    status["held_from_last_scan"] = 6
    path.write_text(json.dumps(status))
    build(project)
    assert json.loads((project / "site/status.json").read_text())["held_from_last_scan"] == 6
    assert "pending_count" not in json.loads((project / "site/status.json").read_text())
