"""Pure local snapshot publication, provider choice, and measured comparison."""

import json
import time
from collections import Counter

from ..places.geometry import destination, distance_m, reverse_map
from ..places.models import Snapshot as GoogleSnapshot
from ..places.pipeline import load_config as places_config
from ..places.storage import utcnow, write_json
from .models import Association, Coverage, PublicData, Snapshot
from .osm import RUNTIME, SNAPSHOT, load_config, runtime
from .spatial import nearby_pairs


def public_paths(root, region_id="kolkata"):
    if (root / "config/regions.yml").exists():
        from ..puja.regions import get_region

        region = get_region(root, region_id)
        return region.food_data, region.provider_data
    return "data/osm_food.json", "data/food_provider.json"


def regional_pandals(root, region_id="kolkata"):
    if not (root / "config/regions.yml").exists():
        return [p for p in places_config(root).pandals if p.enabled]
    from ..places.models import Pandal
    from ..puja.location import effective_location
    from ..puja.pipeline import load_config as catalog
    from ..puja.regions import get_region

    region = get_region(root, region_id)

    return [
        Pandal(
            pandal_id=p.pandal_id,
            name=p.name,
            area=p.area,
            latitude=loc["latitude"],
            longitude=loc["longitude"],
            coordinate_source=loc["coordinate_source"],
            restaurant_radius_m=region.restaurant_radius_m,
            enabled=True,
        )
        for p in catalog(root).published
        for loc in [effective_location(p)]
        if p.region_id == region_id and loc["map_eligible"]
    ]


def read_snapshot(root, region_id="kolkata"):
    for path in (root / runtime(region_id) / SNAPSHOT, root / public_paths(root, region_id)[0]):
        if path.exists():
            raw = json.loads(path.read_text())
            return Snapshot.model_validate(
                {k: v for k, v in raw.items() if k in Snapshot.model_fields}
            )
    raise ValueError("no_osm_snapshot_import_first")


def covered(pandal, bounds):
    return pandal.enabled and all(
        bounds.contains(
            *destination(pandal.latitude, pandal.longitude, pandal.restaurant_radius_m, bearing)
        )
        for bearing in (0, 90, 180, 270)
    )


def associate(root, snapshot=None, region_id="kolkata"):
    snapshot = snapshot or read_snapshot(root, region_id)
    pandals = regional_pandals(root, region_id)
    eligible = [
        p
        for p in pandals
        if covered(p, snapshot.bbox)
        and (
            snapshot.coverage_circles is None
            or any(
                distance_m(p.latitude, p.longitude, c.latitude, c.longitude) + p.restaurant_radius_m
                <= c.radius_m
                for c in snapshot.coverage_circles
            )
        )
    ]
    points = [
        dict(id=p.poi_id, latitude=p.latitude, longitude=p.longitude, name=p.name)
        for p in snapshot.pois
    ]
    start = time.perf_counter()
    pairs = nearby_pairs(eligible, points)
    elapsed = time.perf_counter() - start
    counts = Counter(p[0] for p in pairs)
    result = PublicData(
        **snapshot.model_dump(),
        associations=[
            Association(
                pandal_id=pid,
                poi_id=oid,
                distance_m=round(distance, 1),
                source_snapshot=snapshot.snapshot_id,
            )
            for pid, oid, distance, _ in pairs
        ],
        coverage=[
            Coverage(
                pandal_id=p.pandal_id,
                status="snapshot" if p in eligible else "outside_region",
                radius_m=p.restaurant_radius_m,
                association_count=counts[p.pandal_id],
                anchor_key=f"{p.latitude:.7f},{p.longitude:.7f}",
            )
            for p in sorted(pandals, key=lambda p: p.pandal_id)
        ],
    )
    relative = public_paths(root, region_id)[0]
    for path in (root / relative, root / "site" / relative):
        write_json(path, result.model_dump(mode="json", exclude_none=True))
    return {
        "pois": len(snapshot.pois),
        "associations": len(pairs),
        "mapped_pandals": len(eligible),
        "association_seconds": round(elapsed, 6),
        "per_pandal": dict(sorted(counts.items())),
    }


def build_public(root):
    if not (root / "config/food.yml").exists():
        return
    regions = ["kolkata"]
    if (root / "config/regions.yml").exists():
        from ..puja.regions import build_regions, load_regions

        regions = [r.region_id for r in load_regions(root).regions]
        build_regions(root)
    for region_id in regions:
        build_region(root, region_id)


def build_region(root, region_id):
    config = load_config(root, region_id)
    food_path, provider_path = public_paths(root, region_id)
    # CI/release builds use only the committed OSM subset; operator cache never
    # silently overrides a reviewed snapshot. Import + associate are explicit.
    public = root / food_path
    if public.exists():
        data = PublicData.model_validate_json(public.read_text())
        snapshot = Snapshot.model_validate(data.model_dump(exclude={"associations", "coverage"}))
        associate(root, snapshot, region_id)
    elif config.provider != "google":
        raise ValueError("provider_requires_published_osm_snapshot")
    ids = {p.poi_id for p in data.pois} if public.exists() else set()
    if any(link.poi_id not in ids for link in config.google_enrichment.verified_links):
        raise ValueError("crosswalk_has_unknown_osm_id")
    provider = {
        "schema_version": "food-provider-1",
        "provider": config.provider,
        "initial_display_limit": config.initial_display_limit,
        "google_links": [
            x.model_dump(mode="json") for x in config.google_enrichment.verified_links
        ],
    }
    # Cross-provider identity links are intentionally outside the ODbL dataset.
    for path in (root / provider_path, root / "site" / provider_path):
        write_json(path, provider)


def stats(root, region_id="kolkata"):
    snapshot = read_snapshot(root, region_id)
    named = sum(bool(p.name) for p in snapshot.pois)
    return {
        "snapshot_date": snapshot.snapshot_date.isoformat() if snapshot.snapshot_date else None,
        "snapshot_id": snapshot.snapshot_id,
        "source": str(snapshot.source_url),
        "food_pois": len(snapshot.pois),
        "named": named,
        "named_percent": round(100 * named / len(snapshot.pois), 2) if snapshot.pois else 0,
        "categories": dict(sorted(Counter(p.category for p in snapshot.pois).items())),
        "cuisine_tagged": sum(bool(p.cuisine) for p in snapshot.pois),
        "diagnostics": snapshot.diagnostics,
    }


def distribution(distances):
    values = sorted(distances)
    if not values:
        return None
    return {
        "min_m": round(values[0], 1),
        "median_m": round(values[len(values) // 2], 1),
        "max_m": round(values[-1], 1),
    }


BAKEOFF = (
    "bagbazar-sarbojanin",
    "ekdalia-evergreen-club-durga-puja",
    "chetla-agrani-club-durga-puja",
    "salkia-sadharan-durga-puja",
    "naktala-udayan-sangha-durga-puja",
)


def bakeoff(root, pandal_ids=None, at=None):
    snapshot = read_snapshot(root)
    config = places_config(root)
    selected = set(pandal_ids or BAKEOFF)
    pandals = [p for p in config.pandals if p.enabled and p.pandal_id in selected]
    if len(pandals) != len(selected):
        raise ValueError("bakeoff_requires_known_mapped_pandals")
    if not all(covered(p, snapshot.bbox) for p in pandals):
        raise ValueError("bakeoff_catchment_outside_snapshot")
    cache = root / "data/places-runtime/observations.json"
    google = (
        {k: GoogleSnapshot.model_validate(v) for k, v in json.loads(cache.read_text()).items()}
        if cache.exists()
        else {}
    )
    at = at or utcnow()
    google_pairs = reverse_map(pandals, google, at)
    osm_pairs = nearby_pairs(
        pandals,
        [
            dict(id=p.poi_id, latitude=p.latitude, longitude=p.longitude, name=p.name)
            for p in snapshot.pois
        ],
    )
    pois = {p.poi_id: p for p in snapshot.pois}
    rows = []
    for p in pandals:
        g = [a for a in google_pairs if a["pandal_id"] == p.pandal_id]
        o = [a for a in osm_pairs if a[0] == p.pandal_id]
        items = [pois[a[1]] for a in o]
        rows.append(
            {
                "pandal_id": p.pandal_id,
                "name": p.name,
                "radius_m": p.restaurant_radius_m,
                "google_active_pois": len(g),
                "google_named": None,
                "google_unnamed": None,
                "google_name_note": (
                    "Display names were discarded; named coverage cannot be measured"
                ),
                "google_categories": "restaurant request filter; individual tags unavailable",
                "osm_pois": len(o),
                "osm_named": sum(bool(x.name) for x in items),
                "osm_unnamed": sum(not x.name for x in items),
                "osm_categories": dict(Counter(x.category for x in items)),
                "osm_cuisine_tagged": sum(bool(x.cuisine) for x in items),
                "osm_merged_representations": sum(len(x.merged_osm_ids) for x in items),
                "osm_examples": [
                    {"name": x.name, "source_url": str(x.source_url)} for x in items if x.name
                ][:5],
                "osm_distance": distribution([a[2] for a in o]),
                "google_distance": distribution([a["distance_m"] for a in g]),
            }
        )
    denominator = sum(row["google_active_pois"] for row in rows)
    numerator = sum(row["osm_named"] for row in rows)
    ratio = numerator / denominator if denominator else None
    # All Google IDs are an upper bound on named Google coverage, not a measured
    # named denominator. A sparse OSM result cannot pass by treating unknown as zero.
    decision = (
        "osm"
        if ratio is not None and ratio >= 0.7 and all(r["osm_named"] for r in rows)
        else "hybrid"
        if numerator
        else "google"
    )
    report = {
        "compared_at": at.isoformat(),
        "snapshot_id": snapshot.snapshot_id,
        "rows": rows,
        "osm_named_to_google_all_ratio": round(ratio, 4) if ratio is not None else None,
        "named_google_coverage_measurable": False,
        "suggested_provider": decision,
        "identity_overlap": (
            "Unresolved: no Google names retained; "
            "do not infer Google-only/OSM-only venues from IDs"
        ),
        "google_calls": 0,
        "normalization": snapshot.diagnostics,
    }
    write_json(root / RUNTIME / "bakeoff.json", report)
    return report
