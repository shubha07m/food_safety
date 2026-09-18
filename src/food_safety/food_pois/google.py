"""Optional bounded ID-only suggestions; no automatic cross-provider identity claim."""

import hashlib
import json

import httpx
from pydantic import TypeAdapter

from ..places.client import MAX_RESPONSE_BYTES, RETRYABLE, Client, PlacesError, retry_delay
from ..places.geometry import destination
from ..places.models import PlaceID
from ..places.pipeline import api_key
from ..places.pipeline import load_config as places_config
from ..places.storage import LimitReached, Store, write_json
from .models import PublicData
from .osm import RUNTIME, load_config

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
MASK = "places.id,nextPageToken"


class IDClient(Client):
    def search(self, poi):
        if not poi.name:
            raise PlacesError("id_search_requires_name")
        north, _ = destination(poi.latitude, poi.longitude, 150, 0)
        south, _ = destination(poi.latitude, poi.longitude, 150, 180)
        _, east = destination(poi.latitude, poi.longitude, 150, 90)
        _, west = destination(poi.latitude, poi.longitude, 150, 270)
        payload = {
            "textQuery": poi.name + " West Bengal India",
            "pageSize": 3,
            "locationRestriction": {
                "rectangle": {
                    "low": {"latitude": south, "longitude": west},
                    "high": {"latitude": north, "longitude": east},
                }
            },
        }
        operation = "text-" + hashlib.sha256(poi.poi_id.encode()).hexdigest()[:16]
        with httpx.Client(
            timeout=self.settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
            transport=self.transport,
        ) as client:
            for attempt in range(self.settings.max_retries + 1):
                month = self.store.reserve(operation)
                retry, delay = False, 1.0
                try:
                    with client.stream(
                        "POST",
                        ENDPOINT,
                        json=payload,
                        headers={
                            "X-Goog-Api-Key": self._key,
                            "X-Goog-FieldMask": MASK,
                        },
                    ) as response:
                        if response.status_code != 200:
                            error = f"provider_http_{response.status_code}"
                            retry = response.status_code in RETRYABLE
                            delay = retry_delay(response.headers.get("Retry-After"))
                        else:
                            body = bytearray()
                            for chunk in response.iter_bytes(8192):
                                body.extend(chunk)
                                if len(body) > MAX_RESPONSE_BYTES:
                                    raise PlacesError("response_too_large")
                            if self._key.encode() in body:
                                raise PlacesError("invalid_provider_body")
                            raw = json.loads(body)
                            if not isinstance(raw, dict) or set(raw) - {"places", "nextPageToken"}:
                                raise ValueError("invalid_response")
                            rows = raw.get("places", [])
                            if not isinstance(rows, list) or len(rows) > 3:
                                raise ValueError("invalid_result_count")
                            ids = []
                            for row in rows:
                                if not isinstance(row, dict) or set(row) != {"id"}:
                                    raise ValueError("unexpected_result_fields")
                                ids.append(TypeAdapter(PlaceID).validate_python(row["id"]))
                            self.store.outcome(operation, month)
                            return {
                                "place_ids": sorted(set(ids)),
                                "ambiguous": len(set(ids)) != 1 or bool(raw.get("nextPageToken")),
                                "identity_verified": False,
                            }
                except (httpx.TimeoutException, httpx.NetworkError):
                    error, retry = "provider_transport_error", True
                except httpx.HTTPError:
                    error = "provider_protocol_error"
                except (ValueError, KeyError, PlacesError):
                    error = "malformed_provider_response"
                self.store.outcome(operation, month, error)
                if not retry or delay is None or attempt == self.settings.max_retries:
                    raise PlacesError(error) from None
                self.sleep(delay)
        raise PlacesError("provider_unavailable")


def resolve_ids(root, dry_run=True, transport=None):
    config = load_config(root)
    policy = config.google_enrichment
    data = PublicData.model_validate_json((root / "data/osm_food.json").read_text())
    if set(policy.pandal_ids) - {c.pandal_id for c in data.coverage if c.status == "snapshot"}:
        raise ValueError("enrichment_requires_known_snapshot_catchments")
    ids = {a.poi_id for a in data.associations if a.pandal_id in policy.pandal_ids}
    verified = {x.poi_id for x in policy.verified_links}
    selected = [p for p in data.pois if p.poi_id in ids and p.name and p.poi_id not in verified]
    selected = sorted(selected, key=lambda p: p.poi_id)[: policy.max_unique_pois]
    settings = places_config(root).settings
    store = Store(root, settings, max_calls=policy.max_unique_pois)
    path = root / RUNTIME / "google_id_suggestions.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    hashes = {
        p.poi_id: hashlib.sha256((p.model_dump_json() + MASK).encode()).hexdigest()
        for p in selected
    }
    due = [p for p in selected if hashes[p.poi_id] not in cache]
    report = {
        "enabled": policy.enabled,
        "selected_unique_pois": len(selected),
        "due": len(due),
        "cache_hits": len(selected) - len(due),
        "maximum_attempts": min(
            len(due) * (settings.max_retries + 1),
            policy.max_unique_pois,
            store.status()["remaining"],
        ),
        "calls": 0,
        "results": [],
    }
    if dry_run or not policy.enabled:
        return report
    with store.lock():
        client = IDClient(api_key(root), settings, store, transport)
        for poi in due:
            try:
                result = client.search(poi)
                cache[hashes[poi.poi_id]] = {"poi_id": poi.poi_id, **result}
                write_json(path, cache)
                report["results"].append(
                    {
                        "poi_id": poi.poi_id,
                        "status": "identity_unverified",
                        "id_count": len(result["place_ids"]),
                    }
                )
            except (LimitReached, PlacesError) as exc:
                report["results"].append({"poi_id": poi.poi_id, "status": str(exc)})
                break
    report["calls"] = store.calls
    return report
