import json
import shutil
from pathlib import Path

import httpx
import pytest
import yaml

from food_safety.puja.geocoding import discover, plan, query, summary

ROOT = Path(__file__).resolve().parents[1]


def project(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(ROOT / "config/puja.yml", tmp_path / "config/puja.yml")
    config = yaml.safe_load((tmp_path / "config/puja.yml").read_text())
    config["published"] = config["published"][:2]
    (tmp_path / "config/puja.yml").write_text(yaml.safe_dump(config))
    return tmp_path, config["published"]


def test_geocode_requires_explicit_bounded_valid_selection(tmp_path):
    root, records = project(tmp_path)
    with pytest.raises(ValueError, match="explicit_pandal_ids_required"):
        plan(root, [])
    with pytest.raises(ValueError, match="invalid_pandal_selection"):
        plan(root, ["missing"])
    with pytest.raises(ValueError, match="invalid_geocode_call_limit"):
        discover(root, [records[0]["pandal_id"]], max_calls=31)


def test_geocode_dry_run_is_network_free_and_does_not_publish(tmp_path):
    root, records = project(tmp_path)
    pandal_id = records[1]["pandal_id"]
    result = discover(root, [pandal_id], dry_run=True)
    assert result["expected_calls"] == 1
    assert result["google_requests_made"] == 0
    assert not (root / ".cache").exists()
    assert not (root / "data").exists()


def test_geocode_results_are_private_cached_and_require_review(tmp_path):
    root, records = project(tmp_path)
    pandal_id = records[1]["pandal_id"]
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["User-Agent"].startswith("TheBengalFoodPath/")
        return httpx.Response(
            200,
            json=[
                {
                    "display_name": "Fixture pandal, Howrah, West Bengal, India",
                    "lat": "22.60",
                    "lon": "88.34",
                    "osm_type": "node",
                    "osm_id": 123,
                    "category": "amenity",
                    "type": "place_of_worship",
                }
            ],
        )

    transport = httpx.MockTransport(handler)
    result = discover(root, [pandal_id], transport=transport, sleep=lambda _: None)
    second = discover(root, [pandal_id], transport=transport, sleep=lambda _: None)
    assert result["calls_made"] == 1 and second["calls_made"] == 0
    assert len(requests) == 1
    cache = json.loads((root / ".cache/puja/geocoding.json").read_text())
    assert cache[pandal_id]["status"] == "review_required"
    assert cache[pandal_id]["results"][0]["source_url"] == "https://www.openstreetmap.org/node/123"
    assert summary(root)["publication_requires_curated_config_edit"] is True
    assert not (root / "data").exists()


def test_geocoder_rejects_distant_and_malformed_results(tmp_path):
    root, records = project(tmp_path)
    pandal_id = records[1]["pandal_id"]
    body = [
        {
            "display_name": "Wrong city",
            "lat": "28.6",
            "lon": "77.2",
            "osm_type": "node",
            "osm_id": 1,
        },
        {"display_name": "Incomplete"},
    ]
    discover(
        root,
        [pandal_id],
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=body)),
        sleep=lambda _: None,
    )
    assert summary(root)["statuses"] == {"no_match": 1}


def test_query_uses_name_and_locality_without_coordinates(tmp_path):
    root, records = project(tmp_path)
    from food_safety.puja.pipeline import load_config

    record = {r.pandal_id: r for r in load_config(root).published}[records[1]["pandal_id"]]
    value = query(record)
    assert record.name.split()[0] in value and record.city in value and "India" in value
    assert "Durga Puja" not in value
