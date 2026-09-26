"""Turn private form imports and known changed sources into bounded private seeds."""

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

from ..storage import dump
from .leads import canonical, run
from .pipeline import load_config
from .regions import get_region
from .review_queue import candidates

LABELS = {
    "Kolkata region": "kolkata",
    "California": "california",
    "London region": "london",
    "Toronto / GTA": "toronto",
    "Melbourne": "melbourne",
}
FORM_SEEDS = ".cache/puja/form_suggestions.json"


def submission_seeds(root):
    path = root / FORM_SEEDS
    return json.loads(path.read_text()) if path.exists() else []


def import_form_csv(root: Path, path: Path):
    """Import a Google Form CSV without retaining contact, notes, or raw rows."""
    resolved = path.resolve()
    if resolved.is_relative_to(root.resolve()) and not resolved.is_relative_to(
        (root / ".cache").resolve()
    ):
        raise ValueError("form_csv_must_be_outside_tracked_tree")
    if resolved.stat().st_size > 1024 * 1024:
        raise ValueError("form_csv_too_large")
    with resolved.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) > 500:
        raise ValueError("form_csv_too_many_rows")
    seeds = {(s["region"], s["url"]): s for s in submission_seeds(root)}
    imported, skipped = 0, 0
    for row in rows:
        name = (row.get("Puja / organizer name") or row.get("Puja or organizer name") or "").strip()
        city = (row.get("City / region") or row.get("City or locality") or "").strip()
        label = (row.get("Region") or city).strip()
        region = LABELS.get(label) or (label if label in LABELS.values() else None)
        raw_url = (
            row.get("Official organizer / event URL") or row.get("Official or event URL") or ""
        ).strip()
        if not name or not city or not region or len(name) > 200:
            skipped += 1
            continue
        try:
            url = canonical(raw_url)
        except ValueError:
            skipped += 1
            continue
        seed = {"region": region, "url": url, "candidate_name": name, "origin": "google_form"}
        key = (region, url)
        if key not in seeds:
            imported += 1
        seeds[key] = seed
    if len(seeds) > 500:
        raise ValueError("form_seed_queue_full")
    dump(root / FORM_SEEDS, sorted(seeds.values(), key=lambda s: (s["region"], s["url"])))
    return {"imported": imported, "skipped": skipped, "queued_sources": len(seeds)}


def changed_source_seeds(root):
    path = root / "data/puja_refresh.json"
    receipts = json.loads(path.read_text()).get("sources", {}) if path.exists() else {}
    seeds = []
    for source in load_config(root).sources:
        receipt = receipts.get(source.source_id, {})
        if (
            not source.enabled
            or not receipt.get("pending_change")
            or not receipt.get("content_hash")
        ):
            continue
        get_region(root, source.region_id)
        seeds.append(
            {
                "region": source.region_id,
                "url": str(source.url),
                "source_kind": source.source_kind,
                "origin": "changed_source",
                "refresh_revision": receipt["content_hash"],
                "allow_missing_robots": source.allow_missing_robots,
                "content_selector": source.content_selector,
            }
        )
    return seeds[:20]


def prepare(root: Path, *, max_calls=2):
    """Review startup sync. Provider failures leave existing cards readable."""
    public = submission_seeds(root)
    incomplete = [
        {
            "region": item["region"],
            "url": item["source_url"],
            "mode": "profile",
            "accepted_identity": item["name"],
            "origin": item["origin"],
        }
        for item in candidates(root)
        if item["review_state"] == "pending"
        and not (item.get("fields", {}).get("locality") or {}).get("value")
    ]
    seeds = [*public, *changed_source_seeds(root), *incomplete]
    if not seeds:
        return {"seeds": 0, "model_calls": 0}
    # A monthly campaign bounds repeated startup attempts; revision-aware caches
    # avoid refetching unchanged known sources.
    campaign = "review-intake-" + datetime.now(UTC).strftime("%Y-%m")
    path = root / ".cache/puja/review_intake_seeds.json"
    dump(path, seeds[:40])
    return run(root, path, campaign, max_calls=max_calls)
