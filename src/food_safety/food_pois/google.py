"""Optional bounded ID-only suggestions; no automatic cross-provider identity claim."""

import hashlib
import json
from collections import Counter

import httpx
from pydantic import TypeAdapter

from ..places.client import MAX_RESPONSE_BYTES, RETRYABLE, Client, PlacesError, retry_delay
from ..places.geometry import destination
from ..places.models import PlaceID
from ..places.pipeline import api_key
from ..places.pipeline import load_config as places_config
from ..places.storage import LimitReached, Store, write_json
from .models import PublicData, normalize
from .osm import load_config, runtime

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
MASK = "places.id,nextPageToken"


class IDClient(Client):
    def search(self, poi, context="West Bengal India"):
        if not poi.name:
            raise PlacesError("id_search_requires_name")
        north, _ = destination(poi.latitude, poi.longitude, 150, 0)
        south, _ = destination(poi.latitude, poi.longitude, 150, 180)
        _, east = destination(poi.latitude, poi.longitude, 150, 90)
        _, west = destination(poi.latitude, poi.longitude, 150, 270)
        payload = {
            "textQuery": normalize(poi.name) + " " + context,
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
                                "status": (
                                    "unresolved"
                                    if not ids
                                    else "ambiguous"
                                    if len(set(ids)) != 1 or raw.get("nextPageToken")
                                    else "suggested"
                                ),
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


def resolve_ids(root, dry_run=True, transport=None, region_id="kolkata", execute=False):
    from .pipeline import public_paths

    config = load_config(root, region_id)
    policy = config.google_enrichment
    data = PublicData.model_validate_json((root / public_paths(root, region_id)[0]).read_text())
    if set(policy.pandal_ids) - {c.pandal_id for c in data.coverage if c.status == "snapshot"}:
        raise ValueError("enrichment_requires_known_snapshot_catchments")
    pois = {p.poi_id: p for p in data.pois}
    named = {
        p.poi_id
        for p in data.pois
        if p.name
        and any(c.isalpha() for c in p.name)
        and normalize(p.name)
        not in {
            "unnamed",
            "unknown",
            "n/a",
            "no name",
            "unnamed food place",
            "restaurant on google maps",
        }
    }
    ids = set()
    for pandal_id in policy.pandal_ids:
        rows = sorted(
            (a for a in data.associations if a.pandal_id == pandal_id and a.poi_id in named),
            key=lambda a: (a.distance_m, normalize(pois[a.poi_id].name), a.poi_id),
        )
        ids.update(a.poi_id for a in rows[:20])
    verified = {x.poi_id for x in policy.verified_links}
    selected = [p for p in data.pois if p.poi_id in ids and p.name and p.poi_id not in verified]
    selected = sorted(selected, key=lambda p: p.poi_id)[: policy.max_unique_pois]
    settings = places_config(root).settings
    store = Store(root, settings, max_calls=min(settings.max_calls_per_run, policy.max_unique_pois))
    context = "West Bengal IN"
    if (root / "config/regions.yml").exists():
        from ..puja.regions import get_region

        region = get_region(root, region_id)
        context = f"{region.admin1} {region.country_code}"
    path = root / runtime(region_id) / "google_id_suggestions.json"
    cache = json.loads(path.read_text()) if path.exists() else {}
    hashes = {
        p.poi_id: hashlib.sha256(
            (p.model_dump_json() + MASK + context + ":suggestions-v2").encode()
        ).hexdigest()
        for p in selected
    }
    due = [p for p in selected if hashes[p.poi_id] not in cache]
    report = {
        "enabled": policy.enabled or execute,
        "region_id": region_id,
        "eligible_unique_pois": len(ids),
        "selected_unique_pois": len(selected),
        "due": len(due),
        "cache_hits": len(selected) - len(due),
        "maximum_attempts": min(
            len(due) * (settings.max_retries + 1),
            policy.max_unique_pois,
            settings.max_calls_per_run,
            store.status()["remaining"],
        ),
        "calls": 0,
        "ledger_before": store.status()["calls"],
        "remaining_before": store.status()["remaining"],
        "verification_note": "IDs-only response cannot verify returned name or coordinates",
        "results": [],
    }
    if dry_run or not (policy.enabled or execute):
        return report
    with store.lock():
        client = IDClient(api_key(root), settings, store, transport)
        for poi in due:
            try:
                result = client.search(poi, context)
                cache[hashes[poi.poi_id]] = {"poi_id": poi.poi_id, **result}
                write_json(path, cache)
                report["results"].append(
                    {
                        "poi_id": poi.poi_id,
                        "status": result["status"],
                        "id_count": len(result["place_ids"]),
                    }
                )
            except (LimitReached, PlacesError) as exc:
                report["results"].append({"poi_id": poi.poi_id, "status": str(exc)})
                break
    report["calls"] = store.calls
    report["ledger_after"] = store.status()["calls"]
    report["status_counts"] = dict(
        Counter(
            cache[hashes[p.poi_id]].get("status", "unresolved")
            if hashes[p.poi_id] in cache
            else "unresolved"
            for p in selected
        )
    )
    report["verified_ids_added"] = 0
    return report
