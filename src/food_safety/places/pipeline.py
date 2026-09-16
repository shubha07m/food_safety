"""Explicit festival discovery with zero Google calls during build/remapping."""

import hashlib
import json
import os
from datetime import timedelta

import yaml

from .client import FIELD_MASK, Client, PlacesError
from .geometry import plan, reverse_map
from .models import (
    Association,
    Config,
    PublicData,
    PublicRestaurant,
    Registry,
    Restaurant,
    Snapshot,
    maps_url,
)
from .storage import LimitReached, Store, utcnow, write_json


def load_config(root):
    return Config.model_validate(yaml.safe_load((root / "config/places.yml").read_text()))


def api_key(root):
    """Read only this key; never execute a shell, load other secrets, or mutate environ."""
    if "GOOGLE_MAPS_API_KEY" in os.environ:
        return os.environ["GOOGLE_MAPS_API_KEY"]
    path = root / ".env"
    if path.is_file():
        for line in path.read_text().splitlines():
            key, sep, value = line.removeprefix("export ").partition("=")
            if sep and key.strip() == "GOOGLE_MAPS_API_KEY":
                value = value.strip()
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                return value
    return None


def query_hash(zone, count):
    content = {
        "zone": zone.model_dump(),
        "count": count,
        "mask": FIELD_MASK,
        "type": "restaurant",
        "rank": "DISTANCE",
        "version": 1,
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def read_snapshots(store, zones, count):
    path = store.directory / "observations.json"
    if not path.exists():
        return {}, {}
    raw = json.loads(path.read_text())
    # Validate the entire private cache rather than trusting edited/corrupt timestamps.
    snapshots = {key: Snapshot.model_validate(value) for key, value in raw.items()}
    at = store.clock()
    unexpired = {key: s for key, s in snapshots.items() if s.fetched_at <= at < s.expires_at}
    if unexpired != snapshots:
        write_json(path, {key: s.model_dump(mode="json") for key, s in unexpired.items()})
    hashes = {z.zone_id: query_hash(z, count) for z in zones}
    usable = {key: s for key, s in unexpired.items() if hashes.get(key) == s.query_hash}
    return unexpired, usable


def read_registry(root):
    path = root / "data/places.json"
    if not path.exists():
        return Registry()
    data = PublicData.model_validate_json(path.read_text())
    return Registry(
        restaurants=[
            Restaurant.model_validate(r.model_dump(exclude={"google_maps_url"}))
            for r in data.restaurants
        ],
        associations=data.associations,
    )


def export(root, config, registry):
    curated = {r.place_id: r for r in config.restaurants}
    restaurants = {r.place_id: r for r in registry.restaurants}
    restaurants.update({pid: Restaurant(place_id=pid, curated=r) for pid, r in curated.items()})
    enabled = {p.pandal_id for p in config.pandals if p.enabled}
    result = PublicData(
        pandals=[p for p in config.pandals if p.enabled],
        zones=plan(config),
        restaurants=[
            PublicRestaurant(place_id=pid, curated=curated.get(pid), google_maps_url=maps_url(pid))
            for pid in sorted(restaurants)
        ],
        associations=sorted(
            [a for a in registry.associations if a.pandal_id in enabled],
            key=lambda a: (a.pandal_id, a.place_id),
        ),
    ).model_dump(mode="json")
    for path in (root / "data/places.json", root / "site/data/places.json"):
        if not path.exists() or json.loads(path.read_text()) != result:
            write_json(path, result)
    return result


def build_public(root):
    if not (root / "config/places.yml").exists():
        return
    config = load_config(root)
    # Build also evicts expired private coordinates; never refreshes them over the network.
    store = Store(root, config.settings)
    with store.lock():
        read_snapshots(store, plan(config), config.settings.max_results)
        export(root, config, read_registry(root))


def planned(root, zone_id=None, max_calls=None, clock=utcnow):
    config = load_config(root)
    zones = plan(config)
    if zone_id:
        zones = [z for z in zones if z.zone_id == zone_id]
        if not zones:
            raise ValueError("unknown_or_disabled_zone")
    store = Store(root, config.settings, max_calls, clock)
    status = store.status()
    # Dry-run is read-only: do not initialize files or purge cache.
    path = store.directory / "observations.json"
    cached = json.loads(path.read_text()) if path.exists() else {}
    due = []
    for zone in zones:
        s = Snapshot.model_validate(cached[zone.zone_id]) if zone.zone_id in cached else None
        if (
            not s
            or not s.fetched_at <= clock() < s.expires_at
            or s.query_hash != query_hash(zone, config.settings.max_results)
        ):
            due.append(zone.zone_id)
    return {
        "zones": [z.model_dump() for z in zones],
        "due_zone_ids": due,
        "expected_calls_without_retries": min(len(due), store.max_calls, status["remaining"]),
        "maximum_attempts": min(
            len(due) * (config.settings.max_retries + 1), store.max_calls, status["remaining"]
        ),
        "usage": status,
        "google_requests_made": 0,
    }


def discover(
    root,
    zone_id=None,
    dry_run=False,
    max_calls=None,
    smoke_test=False,
    transport=None,
    clock=utcnow,
    sleep=None,
):
    if dry_run:
        result = planned(root, zone_id, 1 if smoke_test else max_calls, clock)
        if smoke_test and len(result["zones"]) != 1:
            raise ValueError("smoke_test_requires_exactly_one_zone")
        return result
    config = load_config(root)
    zones = plan(config)
    selected = [z for z in zones if zone_id is None or z.zone_id == zone_id]
    if zone_id and not selected:
        raise ValueError("unknown_or_disabled_zone")
    if smoke_test and len(selected) != 1:
        raise ValueError("smoke_test_requires_exactly_one_zone")
    store = Store(root, config.settings, 1 if smoke_test else max_calls, clock)
    results = []
    count = min(10, config.settings.max_results) if smoke_test else config.settings.max_results
    with store.lock():
        cache, usable = read_snapshots(store, zones, count)
        registry = read_registry(root)
        known = {r.place_id: r for r in registry.restaurants}
        associations = {(a.pandal_id, a.place_id): a for a in registry.associations}
        changed = False
        for zone in selected:
            if zone.zone_id in usable and not smoke_test:
                results.append({"zone_id": zone.zone_id, "status": "cached"})
                continue
            try:
                client = Client(
                    api_key(root),
                    config.settings,
                    store,
                    transport,
                    **({"sleep": sleep} if sleep else {}),
                )
                observations, at = client.nearby(zone, count)
            except (PlacesError, LimitReached) as exc:
                results.append({"zone_id": zone.zone_id, "status": "skipped", "reason": str(exc)})
                continue
            snapshot = Snapshot(
                query_hash=query_hash(zone, count),
                fetched_at=at,
                expires_at=at + timedelta(days=config.settings.cache_days),
                observations=observations,
                result_limit_reached=len(observations) == count,
            )
            results.append(
                {
                    "zone_id": zone.zone_id,
                    "status": "fetched",
                    "places_returned": len(observations),
                    "result_limit_reached": snapshot.result_limit_reached,
                }
            )
            if smoke_test:
                # Count usage, but do not persist live test coordinates/IDs/associations.
                continue
            cache[zone.zone_id] = usable[zone.zone_id] = snapshot
            for obs in observations:
                known.setdefault(obs.place_id, Restaurant(place_id=obs.place_id))
            changed = True
        if not smoke_test and (changed or usable):
            if changed:
                write_json(
                    store.directory / "observations.json",
                    {key: s.model_dump(mode="json") for key, s in cache.items()},
                )
            # Also recover durable IDs after an interruption between cache and export writes.
            for snapshot in usable.values():
                for observation in snapshot.observations:
                    known.setdefault(
                        observation.place_id, Restaurant(place_id=observation.place_id)
                    )
            for item in reverse_map(config.pandals, usable, clock()):
                association = Association(
                    pandal_id=item["pandal_id"],
                    place_id=item["place_id"],
                    observed_at=item["fetched_at"],
                )
                associations[(association.pandal_id, association.place_id)] = association
            export(
                root,
                config,
                Registry(
                    restaurants=list(known.values()), associations=list(associations.values())
                ),
            )
        return {
            "attempts": store.calls,
            "smoke_test": smoke_test,
            "zones": results,
            "usage": store.status(),
        }


def remap(root, clock=utcnow):
    config = load_config(root)
    store = Store(root, config.settings, clock=clock)
    with store.lock():
        _, usable = read_snapshots(store, plan(config), config.settings.max_results)
        mappings = reverse_map(config.pandals, usable, clock())
        registry = read_registry(root)
        associations = {(a.pandal_id, a.place_id): a for a in registry.associations}
        known = {r.place_id: r for r in registry.restaurants}
        for snapshot in usable.values():
            for observation in snapshot.observations:
                known.setdefault(observation.place_id, Restaurant(place_id=observation.place_id))
        for item in mappings:
            association = Association(
                pandal_id=item["pandal_id"],
                place_id=item["place_id"],
                observed_at=item["fetched_at"],
            )
            associations[(association.pandal_id, association.place_id)] = association
            known.setdefault(association.place_id, Restaurant(place_id=association.place_id))
        export(
            root,
            config,
            Registry(restaurants=list(known.values()), associations=list(associations.values())),
        )
        # Runtime distances are returned to the operator, NEVER written to public/Git artifacts.
        return {"runtime_only": True, "google_requests_made": 0, "associations": mappings}


def run_command(root, args):
    if args.places_command in {"validate", "plan"}:
        return planned(root)
    if args.places_command == "discover":
        return discover(root, args.zone, args.dry_run, args.max_calls, args.smoke_test)
    if args.places_command == "remap":
        return remap(root)
    config = load_config(root)
    return Store(root, config.settings).status()
