"""One effective anchor contract for publication and local food association.

An annual override is atomic: missing coordinates never inherit a previous venue.
Undated legacy anchors remain explicitly last-known, not current event confirmation.
"""

from datetime import UTC, datetime
from math import isfinite


def effective_location(record, year=None):
    p = record.model_dump(mode="json") if hasattr(record, "model_dump") else record
    year = year or datetime.now(UTC).year
    edition = p.get("edition") or {}
    current = edition.get("year") == year and edition.get("confirmed") is True
    override = edition.get("location")
    source = override if override is not None else p
    stale = bool(edition) and edition.get("year") != year
    # A new unreviewed edition must not inherit legacy coordinates.
    withheld = bool(edition) and not override
    lat, lon = source.get("latitude"), source.get("longitude")
    mapped = (
        p.get("enabled") is not False
        and not stale
        and not withheld
        and isinstance(lat, (int, float))
        and not isinstance(lat, bool)
        and isfinite(lat)
        and abs(lat) <= 90
        and isinstance(lon, (int, float))
        and not isinstance(lon, bool)
        and isfinite(lon)
        and abs(lon) <= 180
        and bool(source.get("coordinate_source"))
    )
    precision = source.get("coordinate_precision")
    return {
        "venue": source.get("venue"),
        "address": source.get("address"),
        "city": source.get("city"),
        "latitude": lat if mapped else None,
        "longitude": lon if mapped else None,
        "coordinate_source": source.get("coordinate_source") if mapped else None,
        "coordinate_precision": precision if mapped else None,
        "status": ("historical" if edition.get("year", 0) < year else "other_edition")
        if stale
        else "current"
        if current and edition.get("venue_reviewed") and override
        else "last_known",
        "map_eligible": bool(mapped),
        "near_me_eligible": bool(mapped and precision == "venue"),
        "directions_eligible": bool(
            mapped and current and edition.get("venue_reviewed") and precision == "venue"
        ),
        "anchor_key": f"{lat:.7f},{lon:.7f}" if mapped else None,
    }
