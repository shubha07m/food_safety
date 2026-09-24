"""Turn public suggestions and known changed sources into bounded private seeds."""

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from ..storage import dump
from .approvals import REPO, github
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


def _answer(body, label):
    match = re.search(
        r"(?m)^### " + re.escape(label) + r"\s*\n(.*?)(?=\n### |\Z)", body or "", re.S
    )
    return match.group(1).strip() if match else ""


def submission_seeds(api=github):
    rows = api("GET", f"repos/{REPO}/issues?state=open&per_page=100")
    if not isinstance(rows, list):
        raise ValueError("invalid_suggestion_listing")
    seeds = []
    for issue in rows:
        if issue.get("pull_request") or not str(issue.get("title", "")).startswith(
            "[Puja suggestion]"
        ):
            continue
        body = issue.get("body") or ""
        region = LABELS.get(_answer(body, "Region"))
        name = _answer(body, "Puja or organizer name")
        city = _answer(body, "City or locality")
        url = _answer(body, "Official or event URL")
        if not region or not name or not city or not url or len(name) > 200:
            continue
        try:
            url = canonical(url)
        except ValueError:
            continue
        # Submitter contact and notes never enter model input or review packets.
        seeds.append(
            {
                "region": region,
                "url": url,
                "origin": "public_suggestion",
                "submission_issue": issue["number"],
            }
        )
    return seeds[:20]


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


def prepare(root: Path, *, max_calls=2, api=github):
    """Review startup sync. Provider failures leave existing cards readable."""
    try:
        public = submission_seeds(api)
    except (RuntimeError, ValueError):
        public = []
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
