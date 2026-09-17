"""Bounded, operator-only Nominatim research; never publishes coordinates."""

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..places.models import Latitude, Longitude
from ..places.storage import write_json
from .pipeline import load_config

ENDPOINT = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TheBengalFoodPath/1.0 (https://github.com/shubha07m/food_safety)"
MAX_CALLS = 30
QUERY_VERSION = 2


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class GeocodeResult(Strict):
    display_name: str = Field(min_length=1, max_length=500)
    latitude: Latitude
    longitude: Longitude
    osm_type: str = Field(pattern=r"^(node|way|relation)$")
    osm_id: int = Field(gt=0)
    category: str = Field(default="", max_length=100)
    result_type: str = Field(default="", max_length=100)

    @model_validator(mode="after")
    def local(self):
        # Current catalog is Kolkata/Howrah only; distant name collisions are not candidates.
        if not 22.30 <= self.latitude <= 22.80 or not 88.10 <= self.longitude <= 88.60:
            raise ValueError("result_outside_kolkata_howrah_bounds")
        return self

    @property
    def source_url(self):
        return f"https://www.openstreetmap.org/{self.osm_type}/{self.osm_id}"


def query(record):
    # Directory names often append festival/committee boilerplate that is absent from OSM.
    # Remove only generic tokens; never infer or translate a locality.
    name = re.sub(
        r"\b(?:sarbojanin|durgotsab|durgotsav|durga\s+puja|committee)\b",
        " ",
        record.name,
        flags=re.IGNORECASE,
    )
    name = re.sub(r"\s+", " ", name).strip().strip(",-").strip() or record.name
    locality = record.neighborhood or (
        record.area if record.location_precision != "source_zone" else ""
    )
    values = (name, locality, record.city, "West Bengal", "India")
    return ", ".join(value for value in values if value)


def _identity(record):
    return hashlib.sha256(f"{QUERY_VERSION}:{query(record)}".encode()).hexdigest()


def _cache(root: Path):
    path = root / ".cache/puja/geocoding.json"
    if not path.exists():
        return path, {}
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError("invalid_geocode_cache")
    return path, value


def _records(root, pandal_ids):
    records = {record.pandal_id: record for record in load_config(root).published}
    if not pandal_ids:
        raise ValueError("explicit_pandal_ids_required")
    if len(pandal_ids) != len(set(pandal_ids)) or set(pandal_ids) - set(records):
        raise ValueError("invalid_pandal_selection")
    return [records[pandal_id] for pandal_id in pandal_ids]


def plan(root: Path, pandal_ids):
    records = _records(root, pandal_ids)
    _, cache = _cache(root)
    items = []
    for record in records:
        identity = _identity(record)
        cached = cache.get(record.pandal_id, {})
        items.append(
            {
                "pandal_id": record.pandal_id,
                "query": query(record),
                "already_mapped": record.latitude is not None,
                "cached": cached.get("query_hash") == identity,
            }
        )
    return {
        "provider": "nominatim.openstreetmap.org",
        "policy": "operator_only_single_thread_cached_review_required",
        "requests_per_second": 1,
        "items": items,
        "expected_calls": sum(not item["cached"] for item in items),
        "google_requests_made": 0,
    }


def discover(root: Path, pandal_ids, max_calls=10, dry_run=False, transport=None, sleep=time.sleep):
    if not 1 <= max_calls <= MAX_CALLS:
        raise ValueError("invalid_geocode_call_limit")
    planned = plan(root, pandal_ids)
    if dry_run:
        return planned
    records = _records(root, pandal_ids)
    path, cache = _cache(root)
    calls = 0
    with httpx.Client(
        timeout=20,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        for record in records:
            identity = _identity(record)
            if cache.get(record.pandal_id, {}).get("query_hash") == identity:
                continue
            if calls >= max_calls:
                break
            if calls:
                sleep(1.05)
            response = client.get(
                ENDPOINT
                + "?"
                + urlencode(
                    {
                        "q": query(record),
                        "format": "jsonv2",
                        "limit": 3,
                        "countrycodes": "in",
                        "addressdetails": 1,
                        "namedetails": 1,
                    }
                )
            )
            calls += 1
            if response.status_code != 200 or len(response.content) > 131072:
                cache[record.pandal_id] = {"query_hash": identity, "status": "provider_error"}
                continue
            try:
                raw = response.json()
                if not isinstance(raw, list) or len(raw) > 3:
                    raise ValueError
                results = []
                for item in raw:
                    try:
                        result = GeocodeResult(
                            display_name=item["display_name"],
                            latitude=item["lat"],
                            longitude=item["lon"],
                            osm_type=item["osm_type"],
                            osm_id=item["osm_id"],
                            category=item.get("category", ""),
                            result_type=item.get("type", ""),
                        )
                        results.append(
                            {
                                **result.model_dump(mode="json"),
                                "source_url": result.source_url,
                            }
                        )
                    except (KeyError, ValueError):
                        continue
                cache[record.pandal_id] = {
                    "query_hash": identity,
                    "query": query(record),
                    "status": "review_required" if results else "no_match",
                    "results": results,
                }
            except (ValueError, TypeError, json.JSONDecodeError):
                cache[record.pandal_id] = {"query_hash": identity, "status": "malformed_response"}
    write_json(path, cache)
    return {
        **planned,
        "calls_made": calls,
        "cache_path": ".cache/puja/geocoding.json",
        "publication_changes": 0,
    }


def summary(root: Path):
    _, cache = _cache(root)
    statuses = {}
    for value in cache.values():
        status = value.get("status", "invalid")
        statuses[status] = statuses.get(status, 0) + 1
    return {
        "cached_queries": len(cache),
        "statuses": statuses,
        "publication_requires_curated_config_edit": True,
    }
