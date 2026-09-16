import json
from pathlib import Path

import pytest

from food_safety.browser_maps import browser_config, build_browser_config

ROOT = Path(__file__).resolve().parents[1]


def test_browser_key_absent_does_not_fall_back_to_places_key(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_BROWSER_KEY", raising=False)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "server-only")
    build_browser_config(tmp_path)
    assert json.loads((tmp_path / "site/maps-config.json").read_text()) == {"browser_key": ""}


def test_ignored_config_is_deterministic_and_explicit(tmp_path, monkeypatch):
    key = "AIza" + "a" * 35  # Synthetic, never a real credential.
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", key)
    build_browser_config(tmp_path)
    first = (tmp_path / "site/maps-config.json").read_bytes()
    build_browser_config(tmp_path)
    assert (tmp_path / "site/maps-config.json").read_bytes() == first
    assert json.loads(first) == {"browser_key": key}
    assert "site/maps-config.json" in (ROOT / ".gitignore").read_text()


@pytest.mark.parametrize("server", ["GOOGLE_MAPS_API_KEY", "GEMINI_API_KEY"])
def test_key_reuse_fails_closed(tmp_path, monkeypatch, server):
    key = "AIza" + "b" * 35
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", key)
    monkeypatch.setenv(server, key)
    with pytest.raises(ValueError, match="separate"):
        build_browser_config(tmp_path)
    assert not (tmp_path / "site/maps-config.json").exists()


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


@pytest.mark.parametrize("leak", [None, "wrong_config", "other_asset", "extra_field"])
def test_public_output_exempts_only_exact_browser_config(tmp_path, monkeypatch, leak):
    from scripts import verify_public_output as gate

    key = "AIza" + "d" * 35
    server = "AIza" + "e" * 35
    monkeypatch.setenv("GOOGLE_MAPS_BROWSER_KEY", key)
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", server)
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    (tmp_path / "data").mkdir()
    for path in [site / "data/events.json", tmp_path / "data/events.json"]:
        path.write_text(json.dumps({"records": []}))
    (site / "_headers").write_text(
        "Content-Security-Policy Strict-Transport-Security X-Content-Type-Options frame-ancestors"
    )
    build_browser_config(tmp_path)
    if leak == "wrong_config":
        (site / "maps-config.json").write_text(json.dumps({"browser_key": server}))
    if leak == "extra_field":
        (site / "maps-config.json").write_text(json.dumps({"browser_key": key, "other": "value"}))
    if leak == "other_asset":
        (site / "oops.js").write_text(key)
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "SITE", site)
    monkeypatch.setattr(gate, "REQUIRED", [])
    monkeypatch.setattr(gate, "validate", lambda _: None)
    if leak:
        with pytest.raises(SystemExit, match="public-output gate failed"):
            gate.main()
    else:
        gate.main()
