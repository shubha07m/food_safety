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


def retain_seeds(root):
    """Persist manual/imported/monitor seeds before retrieval; never drops bad URLs."""
    from .queue_store import STORE, add, read

    state = read(root)
    for seed in [*submission_seeds(root), *changed_source_seeds(root)]:
        name = seed.get("candidate_name") or next(
            (
                p.name
                for p in load_config(root).published
                if any(str(s.source_url) == seed["url"] for s in p.sources)
            ),
            "",
        )
        item = add(
            state,
            region=seed.get("region"),
            url=seed["url"],
            name=name,
            origin=seed.get("origin", "manual"),
            revision=seed.get("refresh_revision"),
        )
        item["fetch_options"] = {
            k: seed[k]
            for k in ("allow_missing_robots", "content_selector", "refresh_revision")
            if k in seed
        }
        revision = seed.get("refresh_revision")
        if revision and item.get("monitor_revision") != revision:
            item["enrichment_attempted"] = False
            item["monitor_revision"] = revision
    dump(root / STORE, state)


def prepare(root: Path, *, max_calls=2):
    """One attempt per relevant revision, using the existing bounded extractor."""
    from .queue_store import STORE, read

    retain_seeds(root)
    state = read(root)
    # Legacy campaign cards join the same durable queue without losing their IDs/evidence.
    for item in candidates(root):
        if item["candidate_id"] not in state["candidates"]:
            state["candidates"][item["candidate_id"]] = item
    pending = [
        i
        for i in candidates(root)
        if i["review_state"] == "pending"
        and i.get("region")
        and i.get("name")
        and i.get("url_usable", True)
        and not state["candidates"][i["candidate_id"]].get("enrichment_attempted")
    ]
    # Small deterministic batches. Unattempted candidates remain for the next startup.
    pending = pending[: max(1, min(5, max_calls))]
    seeds = [
        {
            "region": i["region"],
            "url": i["source_url"],
            "mode": "profile",
            "accepted_identity": i["name"],
            "origin": i["origin"],
            **i.get("fetch_options", {}),
        }
        for i in pending
    ]
    for item in pending:
        state["candidates"][item["candidate_id"]]["enrichment_attempted"] = True
        state["candidates"][item["candidate_id"]]["enrichment_notice"] = (
            "Source not automatically readable"
        )
    dump(root / STORE, state)
    if not seeds:
        return {"seeds": 0, "model_calls": 0}
    # A monthly campaign bounds repeated startup attempts; revision-aware caches
    # avoid refetching unchanged known sources.
    campaign = "review-intake-" + datetime.now(UTC).strftime("%Y-%m")
    path = root / ".cache/puja/review_intake_seeds.json"
    dump(path, seeds[:40])
    result = run(root, path, campaign, max_calls=max_calls)
    # Freeze supported facts onto the candidate. Rendering never depends on a successful run.
    report = root / ".cache/puja/campaigns" / campaign / "review.json"
    if report.exists():
        for source in json.loads(report.read_text()).get("sources", []):
            for extracted in source.get("candidates", []):
                for item in pending:
                    if source["url"] == item["source_url"] and (
                        extracted.get("name", "").casefold() == item["name"].casefold()
                    ):
                        state["candidates"][item["candidate_id"]].update(extracted)
                        state["candidates"][item["candidate_id"]]["enrichment_notice"] = (
                            "Source facts extracted; owner approval required"
                        )
        dump(root / STORE, state)
    return result
