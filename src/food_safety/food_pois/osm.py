"""Bounded regional PBF acquisition and pyosmium normalization (operator only)."""

import hashlib
import json
import unicodedata
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx
import yaml
from pydantic import ValidationError

from ..places.storage import write_json
from .models import Config, OSMFoodPOI, Snapshot, normalize

RUNTIME = "data/osm-runtime"
SNAPSHOT = "normalized_food_pois.json"
NORMALIZATION_VERSION = 1
LIFECYCLES = ("disused", "abandoned", "demolished", "razed", "removed", "construction", "proposed")


def load_config(root):
    return Config.model_validate(yaml.safe_load((root / "config/food.yml").read_text()))


def source_path(root, config):
    path = (root / config.source_path).resolve()
    if not path.is_relative_to((root / RUNTIME).resolve()):
        raise ValueError("download_destination_must_be_runtime")
    return path


def download(root, *, refresh=False, transport=None):
    config = load_config(root).osm
    target = source_path(root, config)
    if target.exists() and not refresh:
        return {"status": "cached", "requests": 0, "bytes": target.stat().st_size}
    url = str(config.source_url)
    # Default public provider only; other providers use a manually obtained local file.
    if config.source_url.scheme != "https" or config.source_url.host != "download.geofabrik.de":
        raise ValueError("use_local_source_for_other_extract_providers")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    requests = 0

    def bounded_host(request):
        nonlocal requests
        if request.url.scheme != "https" or request.url.host != "download.geofabrik.de":
            raise ValueError("extract_redirect_outside_provider")
        requests += 1

    try:
        with httpx.Client(
            timeout=60,
            follow_redirects=True,
            max_redirects=2,
            transport=transport,
            event_hooks={"request": [bounded_host]},
        ) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                if int(response.headers.get("content-length", 0)) > config.max_download_bytes:
                    raise ValueError("extract_exceeds_download_cap")
                count = 0
                with partial.open("wb") as stream:
                    for chunk in response.iter_bytes(1_048_576):
                        count += len(chunk)
                        if count > config.max_download_bytes:
                            raise ValueError("extract_exceeds_download_cap")
                        stream.write(chunk)
        partial.replace(target)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return {"status": "downloaded", "requests": requests, "bytes": count}


def category(tags, config):
    if tags.get("access") in {"private", "no"}:
        return None
    if any(tags.get(k) not in {None, "no", "false", "0"} for k in LIFECYCLES):
        return None
    if any(f"{state}:{key}" in tags for state in LIFECYCLES for key in ("amenity", "shop")):
        return None
    for key, allowed in config.categories.items():
        if tags.get(key) in allowed:
            return tags[key]
    return None


def clean(value):
    if not value or any(ord(c) < 32 and not c.isspace() for c in value):
        return None
    return " ".join(unicodedata.normalize("NFC", value).split()) or None


def make_poi(kind, identifier, tags, lat, lon, method, config, timestamp=None):
    food_category = category(tags, config)
    if not food_category or not config.bbox.contains(lat, lon):
        return None
    try:
        return OSMFoodPOI(
            poi_id=f"osm:{kind}:{identifier}",
            provider_id=f"{kind}/{identifier}",
            osm_type=kind,
            osm_id=identifier,
            name=clean(tags.get("name") or tags.get("name:en") or tags.get("name:bn")),
            name_bn=clean(tags.get("name:bn")),
            latitude=lat,
            longitude=lon,
            category=food_category,
            **{
                key: clean(tags.get(key))
                for key in ("amenity", "shop", "cuisine", "brand", "operator", "opening_hours")
            },
            source_url=f"https://www.openstreetmap.org/{kind}/{identifier}",
            source_timestamp=timestamp,
            coordinate_method=method,
        )
    except ValidationError:
        return None


def interior_point(polygons):
    """Horizontal scanline interior point; even/odd ring parity respects holes.

    Coordinates come from libosmium-assembled polygons. Unlike an arithmetic
    centroid, the selected midpoint lies inside an actual polygon component.
    """
    choices = []
    for rings in polygons:
        ys = sorted({point[1] for ring in rings for point in ring})
        if len(ys) < 2:
            continue
        middle = (ys[0] + ys[-1]) / 2
        # Avoid vertex ambiguities by selecting the nearest inter-vertex level.
        y = min(
            ((a + b) / 2 for a, b in zip(ys, ys[1:], strict=False)), key=lambda v: abs(v - middle)
        )
        intersections = []
        for ring in rings:
            for a, b in zip(ring, ring[1:], strict=False):
                if (a[1] > y) != (b[1] > y):
                    intersections.append(a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
        intersections.sort()
        for left, right in zip(intersections[::2], intersections[1::2], strict=True):
            if right > left:
                choices.append((right - left, y, (left + right) / 2))
    if not choices:
        raise ValueError("area_has_no_interior")
    _, lat, lon = max(choices)
    return lat, lon


def inside(point, polygons):
    x, y = point
    for rings in polygons:
        crossing = False
        for ring in rings:
            for a, b in zip(ring, ring[1:], strict=False):
                if (a[1] > y) != (b[1] > y) and x < a[0] + (y - a[1]) * (b[0] - a[0]) / (
                    b[1] - a[1]
                ):
                    crossing = not crossing
        if crossing:
            return True
    return False


def deduplicate(pois, polygons, members):
    """Exact objects first; merge only equal-name/category representations in an area.

    Same-name chain branches are retained. A name/proximity fuzzy match is never
    enough. Node-in-area or explicit relation membership is required.
    """
    unique = {p.poi_id: p for p in pois}
    removed = set()
    ordered = sorted(
        unique.values(), key=lambda p: ({"relation": 0, "way": 1, "node": 2}[p.osm_type], p.poi_id)
    )
    by_name = {}
    for p in ordered:
        by_name.setdefault((normalize(p.name), p.category), []).append(p)
    for parent in ordered:
        if not parent.name or parent.poi_id in removed or parent.poi_id not in polygons:
            continue
        for child in by_name[(normalize(parent.name), parent.category)]:
            if child.poi_id == parent.poi_id or child.poi_id in removed:
                continue
            duplicate = child.poi_id in members.get(parent.poi_id, set()) or (
                child.osm_type == "node"
                and inside((child.longitude, child.latitude), polygons[parent.poi_id])
            )
            if duplicate:
                removed.add(child.poi_id)
                parent.merged_osm_ids = sorted(set(parent.merged_osm_ids + [child.poi_id]))
    return sorted((p for p in ordered if p.poi_id not in removed), key=lambda p: p.poi_id), len(
        removed
    )


def parse_file(path, config):
    try:
        import osmium
    except ImportError:
        raise RuntimeError(
            "Install optional parser: python -m pip install 'osmium==4.3.1'"
        ) from None
    pois, polygons, members = [], {}, {}
    counters = Counter()
    factory = osmium.geom.GeoJSONFactory()

    class Handler(osmium.SimpleHandler):
        def node(self, obj):
            tags = dict(obj.tags)
            if not category(tags, config):
                return
            if not obj.location.valid():
                counters["invalid_geometry"] += 1
                return
            item = make_poi(
                "node",
                obj.id,
                tags,
                obj.location.lat,
                obj.location.lon,
                "osm_node",
                config,
                obj.timestamp,
            )
            if item:
                pois.append(item)

        def way(self, obj):
            # Closed ways are emitted once by the area callback with original IDs.
            tags = dict(obj.tags)
            if not category(tags, config) or obj.is_closed():
                return
            try:
                nodes = [(n.lon, n.lat) for n in obj.nodes]
                if not nodes:
                    raise ValueError("empty_way")
                lon, lat = nodes[len(nodes) // 2]
                item = make_poi(
                    "way", obj.id, tags, lat, lon, "way_midpoint", config, obj.timestamp
                )
                if item:
                    pois.append(item)
            except (ValueError, osmium.InvalidLocationError):
                counters["invalid_geometry"] += 1

        def relation(self, obj):
            if category(dict(obj.tags), config):
                members[f"osm:relation:{obj.id}"] = {
                    f"osm:way:{m.ref}" for m in obj.members if m.type == "w"
                }
                if obj.tags.get("type") not in {"multipolygon", "boundary"}:
                    counters["unsupported_relation_geometry"] += 1

        def area(self, obj):
            tags = dict(obj.tags)
            if not category(tags, config):
                return
            try:
                geometry = json.loads(factory.create_multipolygon(obj))["coordinates"]
                lat, lon = interior_point(geometry)
                kind = "way" if obj.from_way() else "relation"
                item = make_poi(
                    kind, obj.orig_id(), tags, lat, lon, "polygon_interior", config, obj.timestamp
                )
                if item:
                    pois.append(item)
                    polygons[item.poi_id] = geometry
            except (ValueError, RuntimeError):
                counters["invalid_geometry"] += 1

    handler = Handler()
    handler.apply_file(
        str(path),
        locations=True,
        idx="flex_mem",
        filters=[osmium.filter.KeyFilter("amenity", "shop", "type")],
    )
    counters["raw_region_food_features"] = len(pois)
    normalized, duplicates = deduplicate(pois, polygons, members)
    counters["representation_duplicates_removed"] = duplicates
    counters["canonical_duplicates_removed"] = len(pois) - len({p.poi_id for p in pois})
    return normalized, dict(counters)


def import_snapshot(root, path=None):
    config = load_config(root).osm
    if not config.enabled:
        raise ValueError("osm_disabled")
    path = Path(path) if path else source_path(root, config)
    if not path.is_file():
        raise RuntimeError("Missing local extract; run osm import --download or supply --source")
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    identity = hashlib.sha256(
        (digest + config.model_dump_json() + f":normalization-{NORMALIZATION_VERSION}").encode()
    ).hexdigest()
    output = root / RUNTIME / SNAPSHOT
    if output.exists():
        old = Snapshot.model_validate_json(output.read_text())
        if old.snapshot_id == identity:
            return {"status": "cached", "snapshot_id": identity, "pois": len(old.pois)}
    pois, diagnostics = parse_file(path, config)
    import osmium

    with osmium.io.Reader(str(path), osmium.osm.NOTHING) as reader:
        stamp = reader.header().get("osmosis_replication_timestamp") or None
    result = Snapshot(
        snapshot_id=identity,
        source_sha256=digest,
        source_dataset=config.dataset,
        source_url=config.source_url,
        snapshot_date=stamp,
        extracted_at=datetime.now(UTC),
        bbox=config.bbox,
        pois=pois,
        diagnostics=diagnostics,
    )
    write_json(output, result.model_dump(mode="json", exclude_none=True))
    return {
        "status": "imported",
        "snapshot_id": identity,
        "pois": len(pois),
        "diagnostics": diagnostics,
    }
