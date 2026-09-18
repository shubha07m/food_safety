"""Grid-prefiltered local Haversine joins, shared by OSM and Google pools."""

import math
from collections import defaultdict

from ..places.geometry import distance_m


def nearby_pairs(pandals, points):
    """Points are mappings with id/latitude/longitude/name; no provider I/O."""
    grid = defaultdict(list)
    size = 0.01
    for point in points:
        # Validate before using a coordinate as a bucket index.
        distance_m(point["latitude"], point["longitude"], point["latitude"], point["longitude"])
        grid[(math.floor(point["latitude"] / size), math.floor(point["longitude"] / size))].append(
            point
        )
    result = []
    for p in pandals:
        if not p.enabled or p.latitude is None or p.longitude is None:
            continue
        lat_delta = math.degrees(p.restaurant_radius_m / 6371008.8)
        cos = math.cos(math.radians(min(89.999, abs(p.latitude) + lat_delta)))
        lon_delta = min(180, lat_delta / max(cos, 1e-6))
        candidates = []
        for lat in range(
            math.floor((p.latitude - lat_delta) / size),
            math.floor((p.latitude + lat_delta) / size) + 1,
        ):
            for lon in range(
                math.floor((p.longitude - lon_delta) / size),
                math.floor((p.longitude + lon_delta) / size) + 1,
            ):
                wrapped = math.floor((((lon * size + 180) % 360) - 180) / size + 1e-7)
                candidates.extend(grid.get((lat, wrapped), []))
        for point in candidates:
            distance = distance_m(p.latitude, p.longitude, point["latitude"], point["longitude"])
            if distance <= p.restaurant_radius_m:
                result.append((p.pandal_id, point["id"], distance, point.get("name") or ""))
    return sorted(result, key=lambda x: (x[0], x[2], x[3].casefold(), x[1]))
