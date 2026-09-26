from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_refresh_is_two_hour_bounded_and_release_push_skips_discovery():
    workflow = yaml.load(
        (ROOT / ".github/workflows/update-data.yml").read_text(), Loader=yaml.BaseLoader
    )
    assert workflow["name"] == "Refresh Food Safety Data"
    assert set(workflow["on"]) == {"workflow_dispatch", "schedule", "push"}
    release_only = workflow["on"]["workflow_dispatch"]["inputs"]["release_only"]
    assert release_only["type"] == "boolean"
    assert release_only["default"] == "false"
    assert workflow["on"]["schedule"][0]["cron"] == "17 */2 * * *"
    assert workflow["on"]["push"]["branches"] == ["main"]
    job = workflow["jobs"]["candidates"]
    assert job["env"]["AUTO_PUBLISH"] == "true"
    assert "GOOGLE_MAPS_BROWSER_KEY" not in job["env"]
    runtime_steps = [s for s in job["steps"] if "GOOGLE_MAPS_BROWSER_KEY" in s.get("env", {})]
    assert len(runtime_steps) == 1
    assert (
        runtime_steps[0]["env"]["GOOGLE_MAPS_BROWSER_KEY"]
        == "${{ secrets.GOOGLE_MAPS_BROWSER_KEY }}"
    )
    assert "build_deployment.mjs" in runtime_steps[0]["run"]
    assert job["steps"].index(runtime_steps[0]) > next(
        i for i, s in enumerate(job["steps"]) if s.get("name") == "Commit approved artifacts only"
    )
    assert any(
        step.get("env", {}).get("GEMINI_API_KEY") == "${{ secrets.GEMINI_API_KEY }}"
        for step in job["steps"]
    )
    assert job["permissions"] == {"contents": "write", "issues": "write"}
    approval_step = next(
        s for s in job["steps"] if s.get("name") == "Apply owner-approved Puja catalog updates"
    )
    assert approval_step["env"] == {"GH_TOKEN": "${{ github.token }}"}
    assert "puja publish-approved" in approval_step["run"]
    steps = "\n".join(step.get("run", "") for step in job["steps"])
    assert "--max-articles 20" in steps
    assert "verify_public_output.py" in steps
    assert "git diff --cached --quiet" in steps
    assert "git add ." not in steps
    assert "upload-artifact" not in str(workflow)
    scans = [step for step in job["steps"] if step.get("name", "").startswith("Limited source")]
    assert scans[0]["if"] == "github.event_name != 'push' && inputs.release_only != true"
    puja = [step for step in job["steps"] if step.get("name", "").startswith("Due-only")]
    assert puja[0]["if"] == "github.event_name != 'push' && inputs.release_only != true"
    assert "stage_generated.py --stage" in steps
    assert "git add" not in steps


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
