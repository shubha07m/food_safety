import json
import subprocess
from pathlib import Path

import pytest

from food_safety.browser_maps import browser_config, build_browser_config

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("configured", [False, True])
def test_normal_build_always_writes_blank_config(tmp_path, monkeypatch, configured):
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", "AIza" + "a" * 35 if configured else "")
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "server-only")
    build_browser_config(tmp_path)
    first = (tmp_path / "site/maps-config.json").read_bytes()
    build_browser_config(tmp_path)
    assert (tmp_path / "site/maps-config.json").read_bytes() == first
    assert json.loads(first) == {"browser_key": ""}
    tracked_blank = json.loads((ROOT / "site/maps-config.json").read_text()) == {"browser_key": ""}
    assert tracked_blank


@pytest.mark.parametrize("server", ["GOOGLE_MAPS_API_KEY", "GEMINI_API_KEY"])
def test_runtime_key_reuse_fails_closed(tmp_path, monkeypatch, server):
    key = "AIza" + "b" * 35
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", key)
    monkeypatch.setenv(server, key)
    with pytest.raises(ValueError, match="separate"):
        browser_config(tmp_path)


def test_dotenv_browser_key_is_separate_and_not_logged(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("GOOGLE_MAPS_BROWSER_KEY", raising=False)
    key = "AIza" + "c" * 35
    (tmp_path / ".env").write_text(f"GOOGLE_MAPS_BROWSER_KEY={key}\nGOOGLE_MAPS_API_KEY=server\n")
    assert browser_config(tmp_path) == {"browser_key": key}
    assert not capsys.readouterr().out


def test_invalid_key_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", "<script>bad</script>")
    with pytest.raises(ValueError, match="format"):
        browser_config(tmp_path)


@pytest.mark.parametrize("runtime", [False, True])
@pytest.mark.parametrize("bad", [None, "wrong_config", "other_asset", "extra_field", "gemini"])
def test_public_output_allows_config_only_in_runtime(tmp_path, monkeypatch, runtime, bad):
    from scripts import verify_public_output as gate

    key = "AIza" + "d" * 35
    server = "AIza" + "e" * 35
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", key)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", server)
    monkeypatch.setenv("GEMINI_API_KEY", "private-test-value")
    site = tmp_path / ("artifact" if runtime else "site")
    (site / "data").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    for path in [site / "data/events.json", tmp_path / "data/events.json"]:
        path.write_text(json.dumps({"records": []}))
    (site / "_headers").write_text(
        "Content-Security-Policy Strict-Transport-Security X-Content-Type-Options frame-ancestors"
    )
    config = {"browser_key": key if runtime else ""}
    if bad == "wrong_config":
        config["browser_key"] = server if runtime else key
    if bad == "extra_field":
        config["other"] = "value"
    (site / "maps-config.json").write_text(json.dumps(config))
    if bad in {"other_asset", "gemini"}:
        (site / "oops.js").write_text(key if bad == "other_asset" else "private-test-value")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "SITE", site)
    monkeypatch.setattr(gate, "REQUIRED", [])
    monkeypatch.setattr(gate, "validate", lambda _: None)
    if bad:
        with pytest.raises(SystemExit, match="public-output gate failed"):
            gate.main(runtime=runtime)
    else:
        gate.main(runtime=runtime)


def test_index_and_checkout_checked_independently(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from stage_generated import check

    def git(*args):
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True)

    git("init")
    (tmp_path / "site").mkdir()
    path = tmp_path / "site/maps-config.json"
    key = "AIza" + "x" * 35
    path.write_text(json.dumps({"browser_key": key}))
    git("add", "site/maps-config.json")
    path.write_text('{"browser_key":""}')
    with pytest.raises(ValueError, match="index:site/maps-config.json"):
        check(tmp_path)
    git("add", "site/maps-config.json")
    check(tmp_path)
    path.write_text('{"browser_key":"nonempty"}')
    with pytest.raises(ValueError, match="checkout:site/maps-config.json"):
        check(tmp_path)
    path.write_text('{"browser_key":""}')
    (tmp_path / "other.txt").write_text(key)
    git("add", "other.txt")
    with pytest.raises(ValueError, match="other.txt"):
        check(tmp_path)


def test_generated_staging_uses_allowlist_and_refuses_other_staged_files(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from stage_generated import GENERATED, stage

    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True)

    git("init", "-q")
    (tmp_path / "site/data").mkdir(parents=True)
    (tmp_path / "site/maps-config.json").write_text('{"browser_key":""}')
    (tmp_path / "site/data/events.json").write_text("{}")
    git("add", ".")
    git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.org", "commit", "-qm", "base")
    (tmp_path / "site/data/events.json").write_text('{"updated":true}')
    (tmp_path / "site/unapproved.txt").write_text("operator scratch")
    stage(tmp_path)
    assert git("diff", "--cached", "--name-only").splitlines() == ["site/data/events.json"]
    assert "site/maps-config.json" not in GENERATED
    git("add", "site/unapproved.txt")
    with pytest.raises(ValueError, match="outside the allowlist"):
        stage(tmp_path)
