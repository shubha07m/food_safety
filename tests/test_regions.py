import json
import shutil
from pathlib import Path

import httpx
import pytest
import yaml

from food_safety.food_pois.models import Snapshot
from food_safety.food_pois.osm import load_config as food_config
from food_safety.food_pois.osm import make_poi
from food_safety.food_pois.pipeline import associate, regional_pandals
from food_safety.places.pipeline import load_config as google_config
from food_safety.puja.geocoding import discover
from food_safety.puja.pipeline import load_config
from food_safety.puja.regions import load_regions

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def region_root(tmp_path):
    shutil.copytree(ROOT / "config", tmp_path / "config")
    return tmp_path


def test_migration_keeps_kolkata_ids_and_explicit_california_identity(region_root):
    original = yaml.safe_load((ROOT / "config/puja.yml").read_text())["published"]
    records = load_config(region_root).published
    local = [r for r in records if r.region_id == "kolkata"]
    ca = [r for r in records if r.region_id == "california"]
    assert {r.pandal_id for r in local} == {r["pandal_id"] for r in original}
    assert len(local) == 223 and len(ca) == 6
    assert {r.country_code for r in ca} == {"US"}
    assert {r.city for r in ca} == {"Newark", "San Ramon", "Cerritos", "Los Angeles", "Sacramento"}
    assert all(r.sources and r.year == 2026 for r in ca)
    assert sum(r.latitude is not None for r in ca) == 4


def test_region_metadata_and_coordinates_fail_closed(region_root):
    path = region_root / "config/puja-california.yml"
    raw = yaml.safe_load(path.read_text())
    raw["published"][0]["country_code"] = "IN"
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="pandal_region_mismatch"):
        load_config(region_root)
    raw["published"][0]["country_code"] = "US"
    raw["published"][0]["latitude"] = 22.5
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="outside_region"):
        load_config(region_root)


def test_food_provider_paths_and_google_discovery_stay_separate(region_root):
    assert food_config(region_root).provider == "hybrid"
    assert food_config(region_root, "california").provider == "osm"
    with pytest.raises(ValueError, match="unknown_region"):
        food_config(region_root, "missing")
    assert sum(p.enabled for p in google_config(region_root).pandals) == 14
    assert not any(p.pandal_id.startswith("ca-") for p in google_config(region_root).pandals)
    assert len(regional_pandals(region_root, "california")) == 4


def test_california_local_join_exports_only_its_region_without_network(region_root, monkeypatch):
    def no_network(*args, **kwargs):
        raise AssertionError("local association must not call a provider")

    monkeypatch.setattr(httpx.Client, "request", no_network)
    config = food_config(region_root, "california").osm
    anchor = regional_pandals(region_root, "california")[0]
    poi = make_poi(
        "node",
        123,
        {"amenity": "cafe", "name": "Fixture Cafe"},
        anchor.latitude,
        anchor.longitude,
        "osm_node",
        config,
    )
    snapshot = Snapshot(
        snapshot_id="fixture",
        source_sha256="a" * 64,
        source_dataset="Synthetic fixture",
        source_url=config.source_url,
        extracted_at="2026-09-19T00:00:00Z",
        bbox=config.bbox,
        pois=[poi],
    )
    report = associate(region_root, snapshot, "california")
    assert report["associations"] == 1
    public = json.loads((region_root / "site/data/osm_food_california.json").read_text())
    assert public["associations"][0]["pandal_id"] == anchor.pandal_id
    assert public["pois"][0]["name"] == "Fixture Cafe"
    assert not (region_root / "data/osm_food.json").exists()


def test_california_geocoding_uses_us_and_rejects_kolkata_match(region_root):
    called = []

    def reply(request):
        called.append(request)
        assert request.url.params["countrycodes"] == "us"
        return httpx.Response(
            200,
            json=[
                dict(
                    display_name="Wrong country",
                    lat="22.5",
                    lon="88.3",
                    osm_type="node",
                    osm_id=123,
                )
            ],
        )

    result = discover(region_root, ["ca-sanskriti"], transport=httpx.MockTransport(reply))
    assert result["calls_made"] == 1 and result["publication_changes"] == 0
    cache = json.loads((region_root / ".cache/puja/geocoding.json").read_text())
    assert cache["ca-sanskriti"]["status"] == "no_match"
    assert load_regions(region_root).default_region == "kolkata"


def test_region_registry_requires_unique_ids(region_root):
    path = region_root / "config/regions.yml"
    raw = yaml.safe_load(path.read_text())
    raw["regions"].append(raw["regions"][0])
    path.write_text(yaml.safe_dump(raw))
    with pytest.raises(ValueError, match="invalid_region_registry"):
        load_regions(region_root)


def test_venue_subset_does_not_claim_unsampled_parts_of_california(region_root):
    from food_safety.food_pois.models import CoverageCircle

    config = food_config(region_root, "california").osm
    anchor = regional_pandals(region_root, "california")[0]
    snapshot = Snapshot(
        snapshot_id="fixture",
        source_sha256="a" * 64,
        source_dataset="Fixture catchment",
        source_url=config.source_url,
        extracted_at="2026-09-19T00:00:00Z",
        bbox=config.bbox,
        pois=[],
        coverage_circles=[
            CoverageCircle(latitude=anchor.latitude, longitude=anchor.longitude, radius_m=1500)
        ],
    )
    associate(region_root, snapshot, "california")
    data = json.loads((region_root / "data/osm_food_california.json").read_text())
    coverage = {c["pandal_id"]: c["status"] for c in data["coverage"]}
    assert coverage[anchor.pandal_id] == "snapshot"
    assert "outside_region" in coverage.values()
    assert data["associations"] == []


def test_california_import_cache_includes_venue_locations(region_root, monkeypatch):
    pytest.importorskip("osmium")
    from food_safety.food_pois import osm

    calls = []
    monkeypatch.setattr(osm, "parse_file", lambda *args: (calls.append(True) or [], {}))
    fixture = ROOT / "tests/fixtures/food_pois.osm"
    first = osm.import_snapshot(region_root, fixture, "california")
    assert first["status"] == "imported"
    assert osm.import_snapshot(region_root, fixture, "california")["status"] == "cached"
    path = region_root / "config/puja-california.yml"
    raw = yaml.safe_load(path.read_text())
    raw["published"][0]["latitude"] += 0.001
    path.write_text(yaml.safe_dump(raw))
    assert (
        osm.import_snapshot(region_root, fixture, "california")["snapshot_id"]
        != first["snapshot_id"]
    )
    assert len(calls) == 2


def test_region_export_is_deterministic_and_uses_only_public_fields(region_root):
    from food_safety.puja.regions import build_regions, public_registry

    assert build_regions(region_root) == public_registry(region_root)
    before = (region_root / "site/data/regions.json").read_bytes()
    build_regions(region_root)
    assert (region_root / "site/data/regions.json").read_bytes() == before
    assert b"geocode_bounds" not in before and b"catalog_config" not in before
