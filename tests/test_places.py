"""Synthetic HTTP only: never use live credentials or captured Google payload fixtures."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import yaml
from pydantic import ValidationError

from food_safety.places.client import FIELD_MASK, PlacesError, retry_delay
from food_safety.places.geometry import distance_m, plan, reverse_map
from food_safety.places.models import (
    Config,
    CuratedRestaurant,
    Observation,
    PublicData,
    Settings,
    Snapshot,
    maps_url,
)
from food_safety.places.pipeline import (
    api_key,
    build_public,
    discover,
    load_config,
    planned,
    remap,
)
from food_safety.places.storage import Store

AT = datetime(2026, 9, 15, tzinfo=UTC)
ROOT = Path(__file__).resolve().parents[1]


def pandal(pid="a", longitude=88.36, **changes):
    return {
        "pandal_id": pid,
        "name": f"Synthetic {pid}",
        "area": "Synthetic area",
        "latitude": 22.60,
        "longitude": longitude,
        "enabled": True,
        "coordinate_source": "https://example.org/independent-survey",
        **changes,
    }


def zone(zid="z", members=None, longitude=88.36, **changes):
    return {
        "zone_id": zid,
        "name": "Synthetic zone",
        "center_latitude": 22.60,
        "center_longitude": longitude,
        "radius_m": 500,
        "pandal_ids": members or ["a"],
        **changes,
    }


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "fixture-key")
    (tmp_path / "config").mkdir()
    configure(tmp_path)
    return tmp_path


def configure(root, **changes):
    value = {"pandals": [pandal()], "zones": [zone()], **changes}
    (root / "config/places.yml").write_text(yaml.safe_dump(value))


def response(pid="synthetic_place", longitude=88.36):
    # Fabricated response schema, not captured provider content.
    return {
        "places": [
            {
                "id": pid,
                "displayName": {"text": "Synthetic provider name"},
                "location": {"latitude": 22.60, "longitude": longitude},
            }
        ]
    }


def run(root, handler=None, **kwargs):
    return discover(
        root,
        transport=httpx.MockTransport(
            handler or (lambda request: httpx.Response(200, json=response()))
        ),
        clock=kwargs.pop("clock", lambda: AT),
        sleep=lambda _: None,
        **kwargs,
    )


def test_haversine():
    assert distance_m(0, 0, 0, 0) == 0
    assert distance_m(0, 0, 0, 1) == pytest.approx(111195.08, rel=1e-5)
    assert distance_m(0, 179.999, 0, -179.999) < 223
    assert distance_m(90, 0, -90, 0) == pytest.approx(20015114, rel=1e-6)
    with pytest.raises(ValueError):
        distance_m(float("nan"), 0, 0, 0)
    with pytest.raises(ValueError):
        distance_m(91, 0, 0, 0)


@pytest.mark.parametrize(
    "change",
    [
        {"pandals": [pandal(), pandal()]},
        {"zones": [zone(), zone()]},
        {"pandals": [pandal(latitude=91)]},
        {"pandals": [pandal(longitude=-181)]},
        {"pandals": [pandal(restaurant_radius_m=0)]},
        {"pandals": [pandal(latitude=None)]},
        {"pandals": [pandal(coordinate_source=None)]},
        {"zones": [zone(radius_m=50001)]},
        {"zones": [zone(radius_m=-1)]},
        {"zones": [zone(members=["missing"])]},
        {"zones": [zone(members=["a", "a"])]},
        {"settings": {"cache_days": 31}},
        {"settings": {"max_results": 21}},
        {"settings": {"monthly_limit": 3001}},
        {"settings": {"warning_threshold": 3001}},
    ],
)
def test_invalid_config(workspace, change):
    configure(workspace, **change)
    with pytest.raises(ValidationError):
        load_config(workspace)


def test_manual_zone_must_cover_catchments(workspace):
    configure(workspace, zones=[zone(radius_m=499)])
    with pytest.raises(ValueError, match="catchment"):
        planned(workspace)


def test_disabled_entries_do_not_become_automatic_zones(workspace):
    configure(
        workspace, pandals=[pandal(), pandal("b", enabled=False)], zones=[zone(enabled=False)]
    )
    assert planned(workspace)["zones"] == []
    assert run(workspace)["attempts"] == 0


def test_deterministic_overlap_grouping_and_large_zone_avoidance():
    config = Config(pandals=[pandal(), pandal("b", 88.362), pandal("c", 88.40)])
    result = plan(config)
    assert len(result) == 2
    assert any(z.pandal_ids == ["a", "b"] for z in result)
    assert all(z.radius_m <= 1500 for z in result)
    assert plan(config.model_copy(update={"pandals": list(reversed(config.pandals))})) == result


def test_disabled_automatic_requires_assignment():
    with pytest.raises(ValueError, match="missing_zone"):
        plan(Config(pandals=[pandal()], settings={"automatic_zones": False}))


def test_reverse_mapping_many_to_many_and_expiry(workspace):
    configure(workspace, pandals=[pandal(), pandal("b", 88.362), pandal("c", 88.40)], zones=[])
    run(workspace)
    result = remap(workspace, lambda: AT)
    assert {a["pandal_id"] for a in result["associations"]} == {"a", "b"}
    # Each search response in this fixture returns the SAME coordinate, not its search center.
    # c is outside radius, despite being returned for that zone.
    assert remap(workspace, lambda: AT + timedelta(days=7))["associations"] == []


def test_global_dedupe_and_local_radius(workspace):
    configure(workspace, pandals=[pandal(), pandal("b", 88.362), pandal("c", 88.40)], zones=[])
    run(workspace)
    public = json.loads((workspace / "data/places.json").read_text())
    assert len(public["restaurants"]) == 1
    result = remap(workspace, lambda: AT)
    assert [a["pandal_id"] for a in result["associations"]] == ["a", "b"]
    assert len(result["associations"][0]["source_zone_ids"]) == 2
    assert result["google_requests_made"] == 0


def test_remapping_sorts_distance_and_excludes_expired():
    def obs(pid, lon, expired=False):
        at = AT - timedelta(days=8) if expired else AT
        return Observation(
            place_id=pid,
            latitude=22.60,
            longitude=lon,
            fetched_at=at,
            expires_at=at + timedelta(days=7),
        )

    snapshot = Snapshot(
        query_hash="x",
        fetched_at=AT,
        expires_at=AT + timedelta(days=7),
        observations=[obs("farther", 88.363), obs("nearer", 88.36)],
        result_limit_reached=False,
    )
    result = reverse_map(Config(pandals=[pandal()]).pandals, {"z": snapshot}, AT)
    assert [r["place_id"] for r in result] == ["nearer", "farther"]
    assert (
        reverse_map(Config(pandals=[pandal()]).pandals, {"z": snapshot}, AT + timedelta(days=7))
        == []
    )


def test_cache_expiry_evicts_coordinates_keeps_ids(workspace):
    run(workspace)
    assert remap(workspace, lambda: AT + timedelta(days=7))["associations"] == []
    assert json.loads((workspace / "data/places-runtime/observations.json").read_text()) == {}
    assert json.loads((workspace / "data/places.json").read_text())["restaurants"]


def test_no_expiry_extension_or_future_observations():
    with pytest.raises(ValidationError):
        Observation(
            place_id="x", latitude=0, longitude=0, fetched_at=AT, expires_at=AT + timedelta(days=31)
        )


def test_dry_run_is_read_only_and_no_http(workspace, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("HTTP attempted")

    monkeypatch.setattr(httpx.Client, "stream", forbidden)
    result = discover(workspace, dry_run=True, clock=lambda: AT)
    assert result["expected_calls_without_retries"] == 1
    assert result["maximum_attempts"] == 2
    assert not (workspace / "data").exists()


def test_minimal_request_and_cache_no_repeat(workspace):
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert str(request.url) == "https://places.googleapis.com/v1/places:searchNearby"
        assert request.headers["X-Goog-FieldMask"] == FIELD_MASK
        body = json.loads(request.content)
        assert body["includedTypes"] == ["restaurant"]
        assert body["maxResultCount"] == 10
        assert body["locationRestriction"]["circle"]["radius"] == 500
        return httpx.Response(200, json=response())

    first = run(workspace, handler)
    second = run(workspace, handler)
    assert first["attempts"] == 1 and second["attempts"] == 0
    assert len(requests) == 1
    assert first["usage"]["calls"] == 1  # Not the count of restaurants.


def test_retries_count_as_attempts_and_auth_not_retried(workspace):
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(503 if len(seen) == 1 else 200, json=response())

    result = run(workspace, handler)
    assert result["attempts"] == result["usage"]["calls"] == 2
    assert result["usage"]["zones"]["z"]["last_fetch_at"] is not None


@pytest.mark.parametrize("status", [400, 401, 403, 404, 302])
def test_nonretryable_error_redacted(workspace, status, caplog):
    result = run(workspace, lambda request: httpx.Response(status, text="fixture-key"))
    assert result["attempts"] == 1
    assert result["zones"][0]["reason"] == f"provider_http_{status}"
    assert "fixture-key" not in json.dumps(result) + caplog.text
    assert "fixture-key" not in (workspace / "data/places-runtime/usage.json").read_text()


def test_timeout_and_attempt_cap(workspace):
    def handler(request):
        raise httpx.ReadTimeout("fixture-key should never escape", request=request)

    result = run(workspace, handler, max_calls=1)
    assert result["attempts"] == 1
    assert result["zones"][0]["reason"] == "run_limit"
    assert "fixture-key" not in json.dumps(result)


def test_monthly_guard_and_rollover(workspace):
    configure(workspace, settings={"monthly_limit": 1, "warning_threshold": 1})
    first = run(workspace, lambda r: httpx.Response(403))
    assert first["usage"]["warning"]
    assert run(workspace)["attempts"] == 0
    result = run(workspace, clock=lambda: AT + timedelta(days=31))
    assert result["attempts"] == result["usage"]["calls"] == 1


def test_per_run_limit_across_zones(workspace):
    configure(workspace, pandals=[pandal(), pandal("b", 88.40)], zones=[])
    result = run(workspace, max_calls=1)
    assert result["attempts"] == 1
    assert result["zones"][1]["reason"] == "run_limit"


@pytest.mark.parametrize(
    "body", [[], {"error": "x"}, {"places": None}, {"places": [{"id": "x"}]}, {"places": [None]}]
)
def test_malformed_response_preserves_output(workspace, body):
    run(workspace)
    previous = (workspace / "data/places.json").read_bytes()
    result = run(
        workspace, lambda r: httpx.Response(200, json=body), clock=lambda: AT + timedelta(days=8)
    )
    assert result["zones"][0]["reason"] == "malformed_provider_response"
    assert (workspace / "data/places.json").read_bytes() == previous


def test_empty_results_valid(workspace):
    result = run(workspace, lambda r: httpx.Response(200, json={}))
    assert result["zones"][0]["places_returned"] == 0
    assert remap(workspace, lambda: AT)["associations"] == []


def test_no_restricted_fields_in_public_or_cache(workspace):
    run(workspace)
    for path in [workspace / "data/places.json", workspace / "site/data/places.json"]:
        content = path.read_text()
        data = PublicData.model_validate_json(content)
        for restaurant in data.restaurants:
            assert set(restaurant.model_dump()) == {
                "place_id",
                "source",
                "curated",
                "google_maps_url",
            }
        assert "displayName" not in content and "Synthetic provider name" not in content
        assert "distance_m" not in content and "fixture-key" not in content
    cache = (workspace / "data/places-runtime/observations.json").read_text()
    assert "displayName" not in cache and "Synthetic provider name" not in cache


def test_public_model_rejects_google_coordinates_on_restaurant(workspace):
    run(workspace)
    data = json.loads((workspace / "data/places.json").read_text())
    data["restaurants"][0]["latitude"] = 22.60
    with pytest.raises(ValidationError):
        PublicData.model_validate(data)


def test_independent_names_only(workspace):
    with pytest.raises(ValidationError):
        CuratedRestaurant(place_id="x", name="Name", independent_source="https://maps.google.com/")
    configure(
        workspace,
        restaurants=[
            {
                "place_id": "synthetic_place",
                "name": "Curated name",
                "independent_source": "https://example.org/menu",
            }
        ],
    )
    run(workspace)
    assert "Curated name" in (workspace / "site/data/places.json").read_text()


def test_maps_handoff():
    url = urlsplit(maps_url("synthetic_ID-123"))
    assert url.scheme == "https" and url.netloc == "www.google.com"
    assert parse_qs(url.query) == {
        "api": ["1"],
        "query": ["restaurant"],
        "query_place_id": ["synthetic_ID-123"],
    }
    with pytest.raises(ValidationError):
        maps_url("id&key=unsafe")


def test_smoke_only_usage_persisted(workspace):
    result = run(workspace, smoke_test=True)
    assert result["attempts"] == 1
    assert not (workspace / "data/places.json").exists()
    assert not (workspace / "data/places-runtime/observations.json").exists()
    assert (workspace / "data/places-runtime/usage.json").exists()


def test_missing_key_fails_without_request(workspace, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY")
    assert run(workspace)["attempts"] == 0


def test_env_loading_no_shell_evaluation(workspace, monkeypatch):
    monkeypatch.delenv("GOOGLE_MAPS_API_KEY")
    (workspace / ".env").write_text("GOOGLE_MAPS_API_KEY='fixture-key'\nGEMINI_API_KEY=unused\n")
    assert api_key(workspace) == "fixture-key"
    monkeypatch.setenv("GOOGLE_MAPS_API_KEY", "override")
    assert api_key(workspace) == "override"


def test_corrupt_or_missing_initialized_ledger_fails_closed(workspace):
    run(workspace)
    ledger = workspace / "data/places-runtime/usage.json"
    ledger.write_text("not json")
    with pytest.raises(ValueError):
        run(workspace)
    ledger.unlink()
    with pytest.raises(ValueError, match="missing_usage_ledger"):
        run(workspace)


def test_ledger_reservation_precedes_http_and_lock_prevents_concurrent_run(workspace):
    def handler(request):
        ledger = json.loads((workspace / "data/places-runtime/usage.json").read_text())
        assert ledger["months"]["2026-09"]["calls"] == 1
        with pytest.raises(BlockingIOError), Store(workspace, Settings()).lock():
            pass
        return httpx.Response(200, json={})

    run(workspace, handler)


def test_retry_after_long_delay_no_early_retry(workspace):
    result = run(workspace, lambda r: httpx.Response(429, headers={"Retry-After": "120"}))
    assert result["attempts"] == 1
    assert retry_delay("invalid") is None
    assert retry_delay("2") == 2


def test_build_never_calls_google_and_existing_map_untouched(workspace, monkeypatch):
    monkeypatch.setattr(httpx.Client, "stream", lambda *a, **k: pytest.fail("network"))
    build_public(workspace)
    content = (ROOT / "site/geography.mjs").read_text()
    assert "places.json" not in content and "googleapis" not in content
    assert "data/places-runtime/" in (ROOT / ".gitignore").read_text()


def test_target_zone_selection_and_stale_query(workspace):
    with pytest.raises(ValueError, match="unknown_or_disabled_zone"):
        run(workspace, zone_id="missing")
    run(workspace)
    configure(workspace, zones=[zone(radius_m=600)])
    assert run(workspace, zone_id="z")["attempts"] == 1


def test_expired_data_cannot_be_extended_by_remap(workspace):
    run(workspace)
    before = (workspace / "data/places-runtime/observations.json").read_bytes()
    remap(workspace, lambda: AT + timedelta(days=1))
    assert (workspace / "data/places-runtime/observations.json").read_bytes() == before


def test_no_raw_live_response_fixtures():
    assert not list((ROOT / "tests/fixtures").glob("*google*"))


def test_client_error_has_only_safe_code():
    assert str(PlacesError("provider_http_403")) == "provider_http_403"


def test_reserve_persists_before_crash_and_refuses_clock_rollback(workspace):
    store = Store(workspace, Settings(), clock=lambda: AT)
    with store.lock():
        store.reserve("z")  # Simulated interruption before the HTTP request.
    assert store.status()["calls"] == 1
    result = run(workspace, clock=lambda: AT - timedelta(hours=1))
    assert result["attempts"] == 0
    assert result["zones"][0]["reason"] == "clock_moved_backwards"


def test_interrupted_export_recovers_from_cache_without_refetch(workspace, monkeypatch):
    from food_safety.places import pipeline

    original = pipeline.export

    def interrupted(*args):
        raise OSError("synthetic interruption")

    monkeypatch.setattr(pipeline, "export", interrupted)
    with pytest.raises(OSError):
        run(workspace)
    monkeypatch.setattr(pipeline, "export", original)
    assert run(workspace)["attempts"] == 0
    assert len(json.loads((workspace / "data/places.json").read_text())["restaurants"]) == 1


def test_oversized_and_invalid_json_response(workspace):
    result = run(workspace, lambda r: httpx.Response(200, text="x" * 131073))
    assert result["zones"][0]["reason"] == "response_too_large"
    result = run(workspace, lambda r: httpx.Response(200, text="not json"))
    assert result["zones"][0]["reason"] == "malformed_provider_response"


def test_provider_cannot_echo_key_into_place_id(workspace):
    result = run(workspace, lambda r: httpx.Response(200, json=response(pid="fixture-key")))
    assert result["zones"][0]["reason"] == "provider_echoed_credential"
    assert not (workspace / "data/places.json").exists()


def test_cli_dry_run_and_smoke_cap(workspace, monkeypatch, capsys):
    from food_safety import cli

    monkeypatch.setattr(cli, "ROOT", workspace)
    monkeypatch.setattr(
        "sys.argv",
        ["food-safety", "places", "discover", "--dry-run", "--smoke-test", "--zone", "z"],
    )
    cli.main()
    result = json.loads(capsys.readouterr().out)
    assert result["maximum_attempts"] == 1
    assert not (workspace / "data").exists()


def test_multiple_restaurants_are_one_call(workspace):
    payload = {"places": response("one")["places"] + response("two")["places"]}
    result = run(workspace, lambda r: httpx.Response(200, json=payload))
    assert result["zones"][0]["places_returned"] == 2
    assert result["usage"]["calls"] == 1


def test_expired_cache_never_restored_on_failed_refresh(workspace):
    run(workspace)
    result = run(workspace, lambda r: httpx.Response(403), clock=lambda: AT + timedelta(days=8))
    assert result["zones"][0]["reason"] == "provider_http_403"
    assert remap(workspace, lambda: AT + timedelta(days=8))["associations"] == []


def test_retry_after_short_delay_used(workspace):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        return (
            httpx.Response(429, headers={"Retry-After": "2"})
            if len(calls) == 1
            else httpx.Response(200, json={})
        )

    result = discover(
        workspace, transport=httpx.MockTransport(handler), clock=lambda: AT, sleep=sleeps.append
    )
    assert result["attempts"] == 2 and sleeps == [2]


def test_public_dataset_rejects_extra_fields_and_bad_links(workspace):
    run(workspace)
    data = json.loads((workspace / "data/places.json").read_text())
    data["associations"][0]["distance_m"] = 12
    with pytest.raises(ValidationError):
        PublicData.model_validate(data)
    del data["associations"][0]["distance_m"]
    data["restaurants"][0]["google_maps_url"] = "https://example.org/not-maps"
    with pytest.raises(ValidationError):
        PublicData.model_validate(data)


@pytest.mark.parametrize("command", ["validate", "plan", "remap", "usage"])
def test_cli_read_and_local_commands_after_realistic_usage(workspace, monkeypatch, capsys, command):
    from food_safety import cli

    run(workspace)
    monkeypatch.setattr(cli, "ROOT", workspace)
    monkeypatch.setattr("sys.argv", ["food-safety", "places", command])
    cli.main()
    assert isinstance(json.loads(capsys.readouterr().out), dict)


def test_pandal_coordinates_cannot_claim_google_as_independent_source():
    with pytest.raises(ValidationError):
        Config(pandals=[pandal(coordinate_source="https://maps.google.com/")])
