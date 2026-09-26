"""Private candidate-first intake; OAuth tokens are not editorial state."""

import hashlib
import json
import re
from pathlib import Path

from ..storage import dump
from .leads import canonical, norm
from .regions import load_regions

STORE = ".cache/puja/queue.json"


def read(root):
    path = root / STORE
    return json.loads(path.read_text()) if path.exists() else {"candidates": {}, "responses": {}}


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def region_for(root, locality):
    from .pipeline import load_config

    text = norm(locality)
    matches = set()
    for r in load_regions(root).regions:
        labels = [r.region_id, r.label]
        if any(re.search(r"\b" + re.escape(norm(label)) + r"\b", text) for label in labels):
            matches.add(r.region_id)
    if not matches:
        matches = {p.region_id for p in load_config(root).published if norm(p.city) == text}
    return next(iter(matches)) if len(matches) == 1 else None


def add(state, *, region, url, name, locality="", origin="manual", revision=None):
    """Malformed URLs remain data, never executable links or fetch targets."""
    try:
        normalized = canonical(url)
        readable = True
    except ValueError:
        normalized, readable = url.strip(), False
    key = (
        "pc-"
        + hashlib.sha256(
            "\0".join((region or "unknown", normalized, norm(name))).encode()
        ).hexdigest()[:20]
    )
    if key not in state["candidates"]:
        state["candidates"][key] = {
            "candidate_id": key,
            "origin": origin,
            "name": name[:200],
            "region": region,
            "locality": locality[:160],
            "source_url": normalized,
            "source_title": "Owner-submitted Puja source",
            "source_type": "unknown",
            "source_revision": revision or digest([normalized, name, locality]),
            "monitor_revision": None,
            "fields": {},
            "summaries": {},
            "duplicate_ids": [],
            "same_source_listing_ids": [],
            "warnings": [],
            "proposed_tier": "source_listed_candidate",
            "map_eligibility": "not_reviewed",
            "url_usable": readable,
            "enrichment_attempted": False,
            "enrichment_notice": "Awaiting source enrichment"
            if readable
            else "Source not automatically readable",
            "campaign": "candidate-first",
        }
    return state["candidates"][key]


def ingest_responses(root: Path, rows):
    state, added = read(root), 0
    for row in rows:
        # Allowlist only. Contact/email and free text notes never reach the model/public data.
        name = str(row.get("Puja / organizer name") or row.get("Puja or organizer name") or "")
        city = str(row.get("City / region") or row.get("City or region") or "")
        url = str(
            row.get("Official organizer or event URL")
            or row.get("Official organizer / event URL")
            or row.get("Official or event URL")
            or ""
        )
        timestamp = str(row.get("Timestamp") or "")
        if not any((name, city, url)):
            continue
        try:
            url = canonical(url.strip())
        except ValueError:
            url = url.strip()[:2048]
        fingerprint = digest([timestamp, norm(name), norm(city), url])
        if fingerprint in state["responses"]:
            continue
        region = region_for(root, city)
        item = add(
            state,
            region=region,
            url=url,
            name=name.strip(),
            locality=city.strip(),
            origin="google_form",
            revision=fingerprint,
        )
        # A changed response is visible, but never silently replaces an approved revision.
        siblings = [
            r for r in state["responses"].values() if timestamp and r["timestamp"] == timestamp
        ]
        if siblings and "Submission changed; prior decision retained" not in item["warnings"]:
            item["warnings"].append("Submission changed; prior decision retained")
        state["responses"][fingerprint] = {
            "candidate_id": item["candidate_id"],
            "timestamp": timestamp,
        }
        added += 1
    dump(root / STORE, state)
    return {"new": added, "candidates": len(state["candidates"])}
