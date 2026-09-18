"""Pure local geometry; no geocoder, network, or inferred establishment coordinates."""

import hashlib
import math

from .models import Config, Zone


def distance_m(lat1, lon1, lat2, lon2):
    if not all(math.isfinite(x) for x in (lat1, lon1, lat2, lon2)):
        raise ValueError("nonfinite_coordinates")
    if not (
        -90 <= lat1 <= 90 and -90 <= lat2 <= 90 and -180 <= lon1 <= 180 and -180 <= lon2 <= 180
    ):
        raise ValueError("invalid_coordinates")
    a, b = math.radians(lat1), math.radians(lat2)
    h = (
        math.sin((b - a) / 2) ** 2
        + math.cos(a) * math.cos(b) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    )
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1, max(0, h))))


def circle(members):
    lat = sum(p.latitude for p in members) / len(members)
    # Circular mean keeps a group crossing the dateline local.
    lon = math.degrees(
        math.atan2(
            sum(math.sin(math.radians(p.longitude)) for p in members),
            sum(math.cos(math.radians(p.longitude)) for p in members),
        )
    )
    radius = math.ceil(
        max(distance_m(lat, lon, p.latitude, p.longitude) + p.restaurant_radius_m for p in members)
    )
    ids = sorted(p.pandal_id for p in members)
    return Zone(
        zone_id="auto-" + hashlib.sha256("|".join(ids).encode()).hexdigest()[:12],
        name=" / ".join(p.name for p in members)[:200],
        center_latitude=lat,
        center_longitude=lon,
        radius_m=radius,
        pandal_ids=ids,
    )


def destination(latitude, longitude, distance, bearing):
    """Return a deterministic geodesic offset in metres/degrees."""
    angular = distance / 6371008.8
    lat1 = math.radians(latitude)
    lon1 = math.radians(longitude)
    direction = math.radians(bearing)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular)
        + math.cos(lat1) * math.sin(angular) * math.cos(direction)
    )
    lon2 = lon1 + math.atan2(
        math.sin(direction) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), ((math.degrees(lon2) + 180) % 360) - 180


def supplemental_zones(zone, settings):
    """Three bounded offset circles for a saturated primary zone."""
    bearings = (0, 120, 240)[: settings.max_supplemental_searches]
    digest = hashlib.sha256(zone.zone_id.encode()).hexdigest()[:12]
    result = []
    for index, bearing in enumerate(bearings, 1):
        latitude, longitude = destination(
            zone.center_latitude,
            zone.center_longitude,
            settings.supplemental_offset_m,
            bearing,
        )
        result.append(
            Zone(
                zone_id=f"sup-{digest}-{index}",
                name=f"{zone.name} supplemental {index}"[:200],
                center_latitude=latitude,
                center_longitude=longitude,
                radius_m=settings.supplemental_radius_m,
                pandal_ids=zone.pandal_ids,
            )
        )
    return result


def plan(config: Config):
    active = {p.pandal_id: p for p in config.pandals if p.enabled}
    zones = []
    assigned = {pid for z in config.zones for pid in z.pandal_ids}
    for zone in config.zones:
        members = [active[pid] for pid in zone.pandal_ids if pid in active]
        if not zone.enabled or not members:
            continue
        if any(
            distance_m(zone.center_latitude, zone.center_longitude, p.latitude, p.longitude)
            + p.restaurant_radius_m
            > zone.radius_m + 0.01
            for p in members
        ):
            raise ValueError("manual_zone_does_not_cover_member_catchment")
        zones.append(zone.model_copy(update={"pandal_ids": [p.pandal_id for p in members]}))
    remaining = [p for pid, p in sorted(active.items()) if pid not in assigned]
    if remaining and not config.settings.automatic_zones:
        raise ValueError("enabled_pandal_missing_zone")
    groups = []
    for pandal in remaining:
        for group in groups:
            # Complete-link overlap prevents a chain growing into one giant circle.
            if all(
                distance_m(pandal.latitude, pandal.longitude, p.latitude, p.longitude)
                <= config.settings.overlap_fraction
                * (pandal.restaurant_radius_m + p.restaurant_radius_m)
                for p in group
            ):
                if circle([*group, pandal]).radius_m <= config.settings.max_zone_radius_m:
                    group.append(pandal)
                    break
        else:
            groups.append([pandal])
    zones.extend(circle(g) for g in groups)
    if len({z.zone_id for z in zones}) != len(zones):
        raise ValueError("generated_zone_id_collision")
    if any(z.radius_m > config.settings.max_zone_radius_m for z in zones):
        raise ValueError("zone_exceeds_practical_radius_limit")
    return sorted(zones, key=lambda z: z.zone_id)


def reverse_map(pandals, snapshots, at):
    """Ephemeral distances only. Newest observation wins; IDs deduplicate globally."""
    places = {}
    for zone_id, snapshot in sorted(snapshots.items()):
        if not snapshot.fetched_at <= at < snapshot.expires_at:
            continue
        for obs in snapshot.observations:
            if not obs.fetched_at <= at < obs.expires_at:
                continue
            previous = places.get(obs.place_id)
            zones = {zone_id} | (previous[1] if previous else set())
            latest = obs if not previous or obs.fetched_at > previous[0].fetched_at else previous[0]
            places[obs.place_id] = (latest, zones)
    from ..food_pois.spatial import nearby_pairs

    mapped = []
    points = [
        {"id": pid, "latitude": obs.latitude, "longitude": obs.longitude}
        for pid, (obs, _) in places.items()
    ]
    for pandal_id, pid, distance, _ in nearby_pairs(pandals, points):
        obs, zones = places[pid]
        mapped.append(
            {
                "pandal_id": pandal_id,
                "place_id": pid,
                "distance_m": round(distance, 1),
                "source_zone_ids": sorted(zones),
                "fetched_at": obs.fetched_at.isoformat(),
                "expires_at": obs.expires_at.isoformat(),
            }
        )
    return sorted(mapped, key=lambda m: (m["pandal_id"], m["distance_m"], m["place_id"]))
