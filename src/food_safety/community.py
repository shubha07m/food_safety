"""Local import of approved Google Form rows; private submitter data is never retained."""

import csv
import json
from pathlib import Path
from urllib.parse import urlsplit

from .safety import safe_url

TYPES = {
    "inspection / safety evidence",
    "licensing / compliance document",
    "correction",
    "missing source",
}


def import_approved_csv(source, destination, policies):
    allowed = {
        p.domain for p in policies if p.enabled and p.discovery_method != "manual_only"
    }
    rows = []
    with Path(source).open(newline="") as handle:
        for raw in csv.DictReader(handle):
            kind = raw.get("submission type", "").strip().casefold()
            url = safe_url(raw.get("public source URL", "").strip())
            if kind not in TYPES or urlsplit(url).hostname not in allowed:
                continue
            rows.append({"source_url": url, "submission_type": kind})
    unique = list({row["source_url"]: row for row in rows}.values())
    Path(destination).parent.mkdir(parents=True, exist_ok=True)
    Path(destination).write_text(json.dumps({"leads": unique}, indent=2) + "\n")
    return len(unique)


def load_leads(root, policies):
    path = root / "data/tmp/community_leads.json"
    if not path.exists():
        return []
    by_domain = {
        p.domain: p for p in policies if p.enabled and p.discovery_method != "manual_only"
    }
    result = []
    for row in json.loads(path.read_text()).get("leads", [])[:100]:
        try:
            url = safe_url(row["source_url"])
        except (KeyError, ValueError, TypeError):
            continue
        policy = by_domain.get(urlsplit(url).hostname)
        if policy and row.get("submission_type") in TYPES:
            result.append((policy, url))
    return result
