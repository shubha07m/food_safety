"""Explicit festival discovery with zero Google calls during build/remapping."""

import hashlib
import json
import os
from datetime import timedelta

import yaml

from .client import FIELD_MASK, Client, PlacesError
from .geometry import plan, reverse_map, supplemental_zones
from .models import (
    Association,
    Config,
    Discovery,
    PublicData,
    PublicRestaurant,
    Registry,
    Restaurant,
    SearchDiagnostic,
    Snapshot,
    maps_url,
)
from .storage import LimitReached, Store, utcnow, write_json


def load_config(root):
    raw = yaml.safe_load((root / "config/places.yml").read_text())
    puja_path = root / "config/puja.yml"
    if not puja_path.exists():
        return Config.model_validate(raw)
    from ..puja.pipeline import load_config as load_puja_config
    from .models import Pandal, Settings

    settings = Settings.model_validate(raw.get("settings", {}))
    known = {item.get("pandal_id") for item in raw.get("pandals", [])}
    additions = []
    for record in load_puja_config(root).published:
        if record.latitude is None or record.longitude is None or record.pandal_id in known:
            continue
        additions.append(
            Pandal(
                pandal_id=record.pandal_id,
                name=record.name,
                name_bn=record.name_bn,
                area=record.neighborhood or record.area,
                latitude=record.latitude,
                longitude=record.longitude,
                restaurant_radius_m=settings.default_restaurant_radius_m,
                enabled=True,
                coordinate_source=record.coordinate_source,
                notes=f"{record.coordinate_precision} coordinate from curated Puja catalog",
            )
        )
    raw["pandals"] = [*raw.get("pandals", []), *(p.model_dump(mode="json") for p in additions)]
    return Config.model_validate(raw)


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
        discoveries=data.discoveries,
        search_diagnostics=data.search_diagnostics,
    )


def export(root, config, registry):
    curated = {r.place_id: r for r in config.restaurants}
    restaurants = {r.place_id: r for r in registry.restaurants}
    restaurants.update({pid: Restaurant(place_id=pid, curated=r) for pid, r in curated.items()})
    enabled = {p.pandal_id for p in config.pandals if p.enabled}
    primary_zone_ids = {z.zone_id for z in plan(config)}
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
        discoveries=sorted(
            [d for d in registry.discoveries if d.pandal_id in enabled],
            key=lambda d: d.pandal_id,
        ),
        search_diagnostics=sorted(
            [d for d in registry.search_diagnostics if d.zone_id in primary_zone_ids],
            key=lambda d: d.zone_id,
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
        primary = plan(config)
        all_zones = [
            zone
            for item in primary
            for zone in (item, *supplemental_zones(item, config.settings))
        ]
        read_snapshots(store, all_zones, config.settings.max_results)
        export(root, config, read_registry(root))


def _snapshot_is_usable(snapshot, zone, count, at):
    return bool(
        snapshot
        and snapshot.fetched_at <= at < snapshot.expires_at
        and snapshot.query_hash == query_hash(zone, count)
    )


def _adaptive_zones(primary, settings):
    return {
        zone.zone_id: [zone, *supplemental_zones(zone, settings)] for zone in primary
    }


def _active_snapshots(primary, zone_groups, usable):
    active = {}
    for zone in primary:
        snapshot = usable.get(zone.zone_id)
        if not snapshot:
            continue
        active[zone.zone_id] = snapshot
        if snapshot.result_limit_reached:
            for supplemental in zone_groups[zone.zone_id][1:]:
                if supplemental.zone_id in usable:
                    active[supplemental.zone_id] = usable[supplemental.zone_id]
    return active


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
    at = clock()
    groups = _adaptive_zones(zones, config.settings)
    primary_due = []
    supplemental_due = []
    saturated = []
    for zone in zones:
        raw = cached.get(zone.zone_id)
        snapshot = Snapshot.model_validate(raw) if raw else None
        if not _snapshot_is_usable(snapshot, zone, config.settings.max_results, at):
            primary_due.append(zone.zone_id)
            continue
        if not snapshot.result_limit_reached:
            continue
        saturated.append(zone.zone_id)
        for supplemental in groups[zone.zone_id][1:]:
            raw = cached.get(supplemental.zone_id)
            item = Snapshot.model_validate(raw) if raw else None
            if not _snapshot_is_usable(item, supplemental, config.settings.max_results, at):
                supplemental_due.append(supplemental.zone_id)
    minimum_requests = len(primary_due) + len(supplemental_due)
    maximum_requests = (
        len(primary_due) * (1 + config.settings.max_supplemental_searches)
        + len(supplemental_due)
    )
    bounded_requests = min(maximum_requests, store.max_calls, status["remaining"])
    return {
        "zones": [z.model_dump() for z in zones],
        "due_zone_ids": primary_due,
        "due_supplemental_zone_ids": supplemental_due,
        "primary_searches_planned": len(zones),
        "primary_searches_due": len(primary_due),
        "known_saturated_primary_searches": len(saturated),
        "potential_supplemental_searches": (
            len(zones) * config.settings.max_supplemental_searches
        ),
        "supplemental_searches_due": len(supplemental_due),
        "absolute_maximum_requests": len(zones)
        * (1 + config.settings.max_supplemental_searches),
        "expected_calls_without_retries": min(
            minimum_requests, store.max_calls, status["remaining"]
        ),
        "maximum_search_requests_this_run": bounded_requests,
        "maximum_attempts": min(
            maximum_requests * (config.settings.max_retries + 1),
            store.max_calls,
            status["remaining"],
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
    groups = _adaptive_zones(zones, config.settings)
    all_zones = [item for zone in zones for item in groups[zone.zone_id]]
    with store.lock():
        cache, usable = read_snapshots(store, all_zones, count)
        registry = read_registry(root)
        known = {r.place_id: r for r in registry.restaurants}
        associations = {(a.pandal_id, a.place_id): a for a in registry.associations}
        discoveries = {d.pandal_id: d for d in registry.discoveries}
        diagnostics = {d.zone_id: d for d in registry.search_diagnostics}
        changed = False
        client = None

        def nearby(search_zone):
            nonlocal client
            if client is None:
                client = Client(
                    api_key(root),
                    config.settings,
                    store,
                    transport,
                    **({"sleep": sleep} if sleep else {}),
                )
            return client.nearby(search_zone, count)

        for zone in selected:
            calls_before = store.calls
            fetched = []
            supplemental_stop_reason = None
            primary = usable.get(zone.zone_id) if not smoke_test else None
            status = "cached" if primary else "fetched"
            if not primary:
                try:
                    observations, at = nearby(zone)
                except (PlacesError, LimitReached) as exc:
                    results.append(
                        {"zone_id": zone.zone_id, "status": "skipped", "reason": str(exc)}
                    )
                    continue
                primary = Snapshot(
                    query_hash=query_hash(zone, count),
                    fetched_at=at,
                    expires_at=at + timedelta(days=config.settings.cache_days),
                    observations=observations,
                    result_limit_reached=len(observations) == count,
                )
                fetched.append(zone.zone_id)
                if smoke_test:
                    results.append(
                        {
                            "zone_id": zone.zone_id,
                            "status": "fetched",
                            "places_returned": len(observations),
                            "result_limit_reached": primary.result_limit_reached,
                        }
                    )
                    continue
                cache[zone.zone_id] = usable[zone.zone_id] = primary
                changed = True
            active_group = {zone.zone_id: primary}
            if primary.result_limit_reached:
                for supplemental in groups[zone.zone_id][1:]:
                    snapshot = usable.get(supplemental.zone_id)
                    if not snapshot:
                        try:
                            observations, at = nearby(supplemental)
                        except (PlacesError, LimitReached) as exc:
                            supplemental_stop_reason = str(exc)
                            break
                        snapshot = Snapshot(
                            query_hash=query_hash(supplemental, count),
                            fetched_at=at,
                            expires_at=at + timedelta(days=config.settings.cache_days),
                            observations=observations,
                            result_limit_reached=len(observations) == count,
                        )
                        cache[supplemental.zone_id] = usable[supplemental.zone_id] = snapshot
                        fetched.append(supplemental.zone_id)
                        changed = True
                    active_group[supplemental.zone_id] = snapshot
            raw_count = sum(len(item.observations) for item in active_group.values())
            unique_ids = {
                observation.place_id
                for item in active_group.values()
                for observation in item.observations
            }
            results.append(
                {
                    "zone_id": zone.zone_id,
                    "status": status,
                    "fetched_zone_ids": fetched,
                    "places_returned": len(primary.observations),
                    "primary_result_count": len(primary.observations),
                    "saturated": primary.result_limit_reached,
                    "result_limit_reached": primary.result_limit_reached,
                    "supplemental_search_count": len(active_group) - 1,
                    "raw_candidate_count": raw_count,
                    "unique_place_count": len(unique_ids),
                    "overlap_ratio": round(
                        (raw_count - len(unique_ids)) / raw_count if raw_count else 0, 4
                    ),
                    "calls_used": store.calls - calls_before,
                    **(
                        {"supplemental_stop_reason": supplemental_stop_reason}
                        if supplemental_stop_reason
                        else {}
                    ),
                }
            )
        if not smoke_test and (changed or usable):
            if changed:
                write_json(
                    store.directory / "observations.json",
                    {key: s.model_dump(mode="json") for key, s in cache.items()},
                )
            # Also recover durable IDs after an interruption between cache and export writes.
            active = _active_snapshots(zones, groups, usable)
            for snapshot in active.values():
                for observation in snapshot.observations:
                    known.setdefault(
                        observation.place_id, Restaurant(place_id=observation.place_id)
                    )
            mappings = reverse_map(config.pandals, active, clock())
            for item in mappings:
                association = Association(
                    pandal_id=item["pandal_id"],
                    place_id=item["place_id"],
                    observed_at=item["fetched_at"],
                )
                associations[(association.pandal_id, association.place_id)] = association
            for result in results:
                if result.get("status") not in {"fetched", "cached"}:
                    continue
                zone = next(item for item in zones if item.zone_id == result["zone_id"])
                snapshot = usable[zone.zone_id]
                association_count = sum(
                    item["pandal_id"] in zone.pandal_ids for item in mappings
                )
                result["associations_created"] = association_count
                observed_at = max(
                    active[item.zone_id].fetched_at
                    for item in groups[zone.zone_id]
                    if item.zone_id in active
                )
                expires_at = min(
                    active[item.zone_id].expires_at
                    for item in groups[zone.zone_id]
                    if item.zone_id in active
                )
                diagnostics[zone.zone_id] = SearchDiagnostic(
                    zone_id=zone.zone_id,
                    observed_at=observed_at,
                    expires_at=expires_at,
                    result_count=result["primary_result_count"],
                    saturated=result["saturated"],
                    supplemental_search_count=result["supplemental_search_count"],
                    raw_candidate_count=result["raw_candidate_count"],
                    unique_place_count_after_dedupe=result["unique_place_count"],
                    associations_created=association_count,
                    overlap_ratio=result["overlap_ratio"],
                    calls_used=result["calls_used"],
                )
                for pandal_id in zone.pandal_ids:
                    discoveries[pandal_id] = Discovery(
                        pandal_id=pandal_id,
                        observed_at=observed_at,
                        expires_at=expires_at,
                        candidates_returned=result["unique_place_count"],
                        result_limit_reached=snapshot.result_limit_reached,
                        primary_result_count=result["primary_result_count"],
                        supplemental_search_count=result["supplemental_search_count"],
                        raw_candidate_count=result["raw_candidate_count"],
                        candidate_unique_count=result["unique_place_count"],
                        association_count=sum(
                            item["pandal_id"] == pandal_id for item in mappings
                        ),
                        saturation_encountered=result["saturated"],
                        overlap_ratio=result["overlap_ratio"],
                        calls_used=result["calls_used"],
                        last_enriched_at=observed_at,
                    )
            export(
                root,
                config,
                Registry(
                    restaurants=list(known.values()),
                    associations=list(associations.values()),
                    discoveries=list(discoveries.values()),
                    search_diagnostics=list(diagnostics.values()),
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
        primary = plan(config)
        groups = _adaptive_zones(primary, config.settings)
        all_zones = [item for zone in primary for item in groups[zone.zone_id]]
        _, usable = read_snapshots(store, all_zones, config.settings.max_results)
        active = _active_snapshots(primary, groups, usable)
        mappings = reverse_map(config.pandals, active, clock())
        registry = read_registry(root)
        associations = {(a.pandal_id, a.place_id): a for a in registry.associations}
        known = {r.place_id: r for r in registry.restaurants}
        for snapshot in active.values():
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
            Registry(
                restaurants=list(known.values()),
                associations=list(associations.values()),
                discoveries=registry.discoveries,
                search_diagnostics=registry.search_diagnostics,
            ),
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
