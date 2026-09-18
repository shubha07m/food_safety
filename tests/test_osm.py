import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import yaml
from pydantic import ValidationError

from food_safety.food_pois.google import IDClient, resolve_ids
from food_safety.food_pois.models import Enrichment, FoodPOI, PublicData, Snapshot
from food_safety.food_pois.osm import (
    category,
    download,
    import_snapshot,
    inside,
    interior_point,
    load_config,
    make_poi,
    parse_file,
)
from food_safety.food_pois.pipeline import associate, bakeoff, build_public, read_snapshot
from food_safety.food_pois.spatial import nearby_pairs
from food_safety.places.models import Pandal, Settings
from food_safety.places.storage import LimitReached, Store, write_json

ROOT = Path(__file__).resolve().parents[1]
AT = datetime(2026, 9, 17, tzinfo=UTC)


@pytest.fixture
def food_root(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "config/food.yml").write_text((ROOT / "config/food.yml").read_text())
    (tmp_path / "config/places.yml").write_text(
        yaml.safe_dump({"pandals": [pandal().model_dump(mode="json")]})
    )
    return tmp_path


def pandal(identifier="a", **kwargs):
    return Pandal(
        pandal_id=identifier,
        name=identifier,
        area="fixture",
        latitude=22.5,
        longitude=88.35,
        enabled=True,
        restaurant_radius_m=600,
        coordinate_source="https://example.org/survey",
        **kwargs,
    )


def poi(root, identifier=1, **kwargs):
    return make_poi(
        "node",
        identifier,
        kwargs.pop("tags", {"amenity": "restaurant", "name": "Synthetic Food"}),
        kwargs.pop("lat", 22.5),
        kwargs.pop("lon", 88.35),
        "osm_node",
        load_config(root).osm,
        AT,
    )


def snapshot(root):
    return Snapshot(
        snapshot_id="fixture",
        source_sha256="a" * 64,
        source_dataset="fixture",
        source_url="https://download.geofabrik.de/asia/india/eastern-zone-latest.osm.pbf",
        snapshot_date=AT,
        extracted_at=AT,
        bbox=load_config(root).osm.bbox,
        pois=[poi(root), poi(root, 2, lat=22.501, tags={"shop": "bakery"})],
    )


def test_pyosmium_nodes_ways_relations_and_embedded_node_dedup(food_root):
    pytest.importorskip("osmium")
    records, diagnostics = parse_file(
        ROOT / "tests/fixtures/food_pois.osm", load_config(food_root).osm
    )
    assert {p.poi_id for p in records} == {
        "osm:node:1",
        "osm:node:2",
        "osm:way:100",
        "osm:relation:300",
    }
    cafe = next(p for p in records if p.poi_id == "osm:way:100")
    assert cafe.coordinate_method == "polygon_interior"
    assert cafe.merged_osm_ids == ["osm:node:14"]
    assert diagnostics["representation_duplicates_removed"] == 1
    assert next(p for p in records if p.poi_id == "osm:node:2").name is None


@pytest.mark.parametrize(
    "tags",
    [
        {"shop": "supermarket"},
        {"amenity": "restaurant", "disused": "yes"},
        {"amenity": "restaurant", "abandoned": "yes"},
        {"amenity": "restaurant", "demolished:amenity": "restaurant"},
        {"amenity": "cafe", "access": "private"},
        {"amenity": "cafe", "access": "no"},
    ],
)
def test_category_and_lifecycle_exclusion(food_root, tags):
    assert category(tags, load_config(food_root).osm) is None


def test_normalized_identity_and_bad_coordinates(food_root):
    value = poi(food_root, tags={"shop": "confectionery", "name:bn": "  মিষ্টি ঘর  "})
    assert value.poi_id == "osm:node:1"
    assert value.name == "মিষ্টি ঘর"
    assert str(value.source_url) == "https://www.openstreetmap.org/node/1"
    assert poi(food_root, lat=float("nan")) is None
    assert poi(food_root, lon=181) is None
    with pytest.raises(ValidationError):
        type(value).model_validate({**value.model_dump(), "provider": "google"})


def test_provider_neutral_runtime_point_cannot_enter_osm_public_data(food_root):
    point = FoodPOI(
        poi_id="google:fixture",
        provider="google",
        provider_id="fixture",
        latitude=22.5,
        longitude=88.35,
    )
    assert point.provider == "google"
    raw = snapshot(food_root).model_dump()
    raw["pois"] = [point.model_dump()]
    with pytest.raises(ValidationError):
        Snapshot.model_validate(raw)
    with pytest.raises(ValidationError):
        FoodPOI(
            poi_id="osm:node:1",
            provider="google",
            provider_id="fixture",
            latitude=22.5,
            longitude=88.35,
        )


def test_polygon_point_respects_holes_and_concavity():
    rings = [
        [[(0, 0), (10, 0), (10, 10), (0, 10), (0, 0)], [(4, 4), (6, 4), (6, 6), (4, 6), (4, 4)]]
    ]
    lat, lon = interior_point(rings)
    assert inside((lon, lat), rings)
    assert not (4 < lon < 6 and 4 < lat < 6)


def test_shared_local_mapping_multiple_pandals_and_order(food_root):
    p = poi(food_root)
    points = [
        {"id": p.poi_id, "latitude": p.latitude, "longitude": p.longitude, "name": p.name},
        {"id": "far", "latitude": 23, "longitude": 89},
    ]
    result = nearby_pairs([pandal(), pandal("b")], points)
    assert [(r[0], r[1], r[2]) for r in result] == [("a", p.poi_id, 0), ("b", p.poi_id, 0)]
    points.append({**points[0], "id": "second", "latitude": 22.501})
    assert [r[1] for r in nearby_pairs([pandal()], points)] == [p.poi_id, "second"]


def test_public_export_deterministic_and_complete_odbl_subset(food_root, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("association must never access providers")

    monkeypatch.setattr(httpx.Client, "send", forbidden)
    snap = snapshot(food_root)
    result = associate(food_root, snap)
    assert result["associations"] == 2
    first = (food_root / "data/osm_food.json").read_bytes()
    associate(food_root, snap)
    assert first == (food_root / "data/osm_food.json").read_bytes()
    data = PublicData.model_validate_json(first)
    assert data.attribution == "© OpenStreetMap contributors"
    assert data.license == "ODbL-1.0"
    assert len(data.pois) == 2
    assert data.associations[0].distance_m == 0
    assert "name" not in json.loads(first)["pois"][1]
    build_public(food_root)
    assert first == (food_root / "data/osm_food.json").read_bytes()


def test_maps_url_has_encoded_name_coordinates_no_key(food_root):
    p = poi(food_root, tags={"amenity": "restaurant", "name": "খাবার & Cafe"})
    params = parse_qs(urlsplit(p.maps_url()).query)
    assert params["api"] == ["1"]
    assert params["query"][0].startswith("খাবার & Cafe")
    assert "key" not in params and "query_place_id" not in params
    assert parse_qs(urlsplit(p.maps_url("verified_id")).query)["query_place_id"] == ["verified_id"]
    with pytest.raises(ValidationError):
        p.maps_url("bad value")


def test_snapshot_import_cache_and_unchanged_inputs(food_root):
    pytest.importorskip("osmium")
    fixture = ROOT / "tests/fixtures/food_pois.osm"
    assert import_snapshot(food_root, fixture)["status"] == "imported"
    before = read_snapshot(food_root).model_dump_json()
    assert import_snapshot(food_root, fixture)["status"] == "cached"
    assert read_snapshot(food_root).model_dump_json() == before


def test_download_cached_and_size_guard(food_root):
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(200, content=b"synthetic pbf")

    transport = httpx.MockTransport(handler)
    assert download(food_root, transport=transport)["requests"] == 1
    assert download(food_root, transport=transport)["requests"] == 0
    assert len(requests) == 1
    with pytest.raises(ValueError, match="cap"):
        download(
            food_root,
            refresh=True,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, headers={"content-length": "999999999999"})
            ),
        )
    assert (food_root / load_config(food_root).osm.source_path).read_bytes() == b"synthetic pbf"


def test_download_redirect_is_bounded_to_extract_provider(food_root):
    with pytest.raises(ValueError, match="outside_provider"):
        download(
            food_root,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(
                    302, headers={"location": "https://example.org/extract.pbf"}
                )
            ),
        )
    assert not (food_root / load_config(food_root).osm.source_path).exists()


def test_public_coverage_count_and_radius_are_validated(food_root):
    associate(food_root, snapshot(food_root))
    raw = json.loads((food_root / "data/osm_food.json").read_text())
    raw["coverage"][0]["association_count"] += 1
    with pytest.raises(ValidationError):
        PublicData.model_validate(raw)
    raw["coverage"][0]["association_count"] -= 1
    raw["associations"][0]["distance_m"] = 601
    with pytest.raises(ValidationError):
        PublicData.model_validate(raw)


def test_grid_join_equals_bruteforce(food_root):
    from food_safety.places.geometry import distance_m

    points = [
        dict(id=str(i), latitude=22.49 + i * 0.00013, longitude=88.34 + (i % 31) * 0.0007)
        for i in range(200)
    ]
    p = pandal()
    expected = {
        r["id"]
        for r in points
        if distance_m(p.latitude, p.longitude, r["latitude"], r["longitude"])
        <= p.restaurant_radius_m
    }
    assert {r[1] for r in nearby_pairs([p], points)} == expected


def test_duplicate_cross_provider_identity_rejected():
    link = {
        "poi_id": "osm:node:1",
        "place_id": "one",
        "identity_source": "https://example.org",
        "verified_at": AT,
        "note": "Explicit operator identity verification",
    }
    with pytest.raises(ValidationError):
        Enrichment(verified_links=[link, {**link, "poi_id": "osm:node:2"}])


def test_id_only_client_does_not_auto_match_and_counts_retries(food_root):
    settings = Settings(max_calls_per_run=3)
    store = Store(food_root, settings, clock=lambda: AT)
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["X-Goog-FieldMask"] == "places.id,nextPageToken"
        assert request.url.path == "/v1/places:searchText"
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"places": [{"id": "synthetic_id"}]})

    with store.lock():
        result = IDClient(
            "test-only", settings, store, httpx.MockTransport(handler), sleep=lambda _: None
        ).search(poi(food_root))
    assert store.status()["calls"] == 2
    assert result["identity_verified"] is False
    assert result["ambiguous"] is False
    assert result["place_ids"] == ["synthetic_id"]


def test_id_only_quota_stops_before_send(food_root):
    settings = Settings(monthly_limit=1, warning_threshold=1, max_calls_per_run=1)
    store = Store(food_root, settings, clock=lambda: AT)
    with store.lock():
        store.reserve("fixture")
        with pytest.raises(LimitReached):
            IDClient(
                "test-only",
                settings,
                store,
                httpx.MockTransport(lambda _: pytest.fail("network called")),
            ).search(poi(food_root))


def test_disabled_id_resolution_does_not_use_google(food_root):
    associate(food_root, snapshot(food_root))
    result = resolve_ids(
        food_root,
        dry_run=False,
        transport=httpx.MockTransport(lambda _: pytest.fail("network called")),
    )
    assert result["calls"] == 0 and result["enabled"] is False


def test_bakeoff_does_not_claim_named_google_coverage(food_root):
    associate(food_root, snapshot(food_root))
    report = bakeoff(food_root, ["a"], AT)
    assert report["google_calls"] == 0
    assert report["named_google_coverage_measurable"] is False
    assert report["suggested_provider"] == "hybrid"


def test_expired_google_pool_is_not_comparison_evidence(food_root):
    associate(food_root, snapshot(food_root))
    write_json(
        food_root / "data/places-runtime/observations.json",
        {
            "zone": {
                "query_hash": "old",
                "fetched_at": (AT - timedelta(days=8)).isoformat(),
                "expires_at": (AT - timedelta(days=1)).isoformat(),
                "observations": [],
                "result_limit_reached": False,
            }
        },
    )
    assert bakeoff(food_root, ["a"], AT)["osm_named_to_google_all_ratio"] is None
