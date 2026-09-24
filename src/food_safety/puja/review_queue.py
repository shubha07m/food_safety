"""Private Puja candidate queue and reviewed, public-safe approval payloads."""

import hashlib
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

from ..storage import dump
from .leads import canonical, norm
from .models import (
    Edition,
    EditionLocation,
    OfficialLink,
    PandalRecord,
    ProgrammeNote,
    SourcedText,
    SourceEvidence,
    SourceSpec,
)
from .pipeline import load_config
from .regions import get_region

DECISIONS = ".cache/puja/review_decisions.json"
ISSUE_MARKER = "<!-- foodpath-puja-approval-v1 -->"
ISSUE_END = "<!-- /foodpath-puja-approval-v1 -->"
OWNER = "shubha07m"
REPO = "shubha07m/food_safety"


def candidate_id(region, source_url, name):
    value = "\0".join((region, canonical(source_url), norm(name)))
    return "pc-" + hashlib.sha256(value.encode()).hexdigest()[:20]


def _packet_candidates(root):
    for path in sorted((root / ".cache/puja/campaigns").glob("*/review.json")):
        try:
            sources = json.loads(path.read_text()).get("sources", [])
        except (OSError, ValueError):
            continue
        for source in sources:
            if source.get("status") != "screened":
                continue
            for item in source.get("candidates", []):
                name = item.get("name")
                if not name:
                    continue
                yield {
                    **item,
                    "candidate_id": candidate_id(source["region"], item["source_url"], name),
                    "origin": source.get("origin", "discovery"),
                    "source_title": source.get("source_title") or urlsplit(source["url"]).hostname,
                    "monitor_revision": source.get("monitor_revision"),
                    "campaign": path.parent.name,
                }


def _legacy_candidates(root):
    for path in sorted((root / ".cache/puja/candidates").glob("*.json")):
        try:
            report = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        for row in report.get("valid_candidates", []):
            required = row.get("required", {})
            name = (required.get("name") or {}).get("value")
            if not name:
                continue
            fields = {
                "name": required.get("name"),
                "locality": required.get("city") or required.get("area"),
                **{
                    key: row.get("optional", {}).get(key)
                    for key in ("organizer", "year", "venue", "address")
                },
            }
            region = report.get("region_id", "kolkata")
            url = report["source_url"]
            yield {
                "candidate_id": candidate_id(region, url, name),
                "origin": "known_source_extraction",
                "name": name,
                "region": region,
                "source_url": url,
                "source_title": report.get("source_title") or urlsplit(url).hostname,
                "source_revision": report["source_revision_id"],
                "monitor_revision": None,
                "source_type": "unknown",
                "fields": fields,
                "summaries": {},
                "duplicate_ids": [],
                "same_source_listing_ids": [],
                "warnings": ["event_year_relationship_requires_review"],
                "proposed_tier": "source_listed_candidate",
                "map_eligibility": "not_reviewed",
                "campaign": "legacy-" + path.stem,
            }


def load_decisions(root):
    path = root / DECISIONS
    return json.loads(path.read_text()) if path.exists() else {}


def save_decision(root, candidate, decision, **details):
    state = load_decisions(root)
    state[candidate["candidate_id"]] = {
        "decision": decision,
        "source_revision": candidate["source_revision"],
        "at": datetime.now(UTC).isoformat(),
        **details,
    }
    dump(root / DECISIONS, state)


def candidates(root):
    state = load_decisions(root)
    rows = {}
    for item in (*_legacy_candidates(root), *_packet_candidates(root)):
        key = item["candidate_id"]
        prior = rows.get(key)
        if not prior or (item["campaign"], item["source_revision"]) > (
            prior["campaign"],
            prior["source_revision"],
        ):
            rows[key] = item
    known = load_config(root).published
    for item in rows.values():
        if not item.get("duplicate_ids"):
            item["duplicate_ids"] = [
                p.pandal_id
                for p in known
                if p.region_id == item["region"]
                and norm(item["name"]) in {norm(p.name), *(norm(a) for a in p.aliases)}
            ]
        if not item.get("same_source_listing_ids"):
            item["same_source_listing_ids"] = [
                p.pandal_id
                for p in known
                if p.region_id == item["region"]
                and any(
                    canonical(str(s.source_url)) == canonical(item["source_url"]) for s in p.sources
                )
            ]
        decision = state.get(item["candidate_id"], {})
        item["review_state"] = (
            decision.get("decision", "pending")
            if decision.get("source_revision") == item["source_revision"]
            else "pending"
        )
    return sorted(
        rows.values(),
        key=lambda row: (row["review_state"] != "pending", row["region"], row["name"].casefold()),
    )


def _field(item, key):
    return (item.get("fields", {}).get(key) or {}).get("value")


def _evidence(item, supported):
    if not supported:
        raise ValueError("missing_supported_fact")
    quote = supported["evidence"]["original_quote"].strip()
    if not quote or len(quote) > 600:
        raise ValueError("evidence_quote_requires_review")
    return SourceEvidence(
        source_url=item["source_url"],
        source_title=item["source_title"],
        publisher=urlsplit(item["source_url"]).hostname,
        quote=quote,
        source_revision_id=item["source_revision"],
    )


def _slug(region, name, existing):
    stem = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")[:48]
    if not stem:
        stem = "puja"
    base = f"{region}-{stem}"
    if base in existing:
        base += "-" + hashlib.sha256(name.encode()).hexdigest()[:6]
    return base


def _date(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def compile_record(root, item, tier, *, at=None):
    """Owner approval chooses the tier; code includes only evidence-backed facts."""
    if tier not in {"source_listed", "current_edition_reviewed"}:
        raise ValueError("invalid_approval_tier")
    region = get_region(root, item["region"])
    name = _field(item, "name") or item["name"]
    locality = _field(item, "locality") or _field(item, "city") or _field(item, "area")
    if not locality or not item.get("source_revision"):
        raise ValueError("identity_region_evidence_incomplete")
    if item.get("duplicate_ids") and len(item["duplicate_ids"]) > 1:
        raise ValueError("ambiguous_existing_identity")
    if item.get("same_source_listing_ids") and (
        not item.get("duplicate_ids")
        or any(identity != item["duplicate_ids"][0] for identity in item["same_source_listing_ids"])
    ):
        raise ValueError("shared_source_identity_requires_review")
    if any(
        w in item.get("warnings", [])
        for w in ("date_year_conflict", "timezone_region_mismatch", "country_code_region_mismatch")
    ):
        raise ValueError("conflicting_source_facts")
    config = load_config(root)
    existing = {p.pandal_id: p for p in config.published}
    target = item.get("duplicate_ids", [])
    base = existing[target[0]] if target else None
    if base and (
        base.region_id != region.region_id
        or norm(base.name) != norm(name)
        and norm(name) not in {norm(a) for a in base.aliases}
    ):
        raise ValueError("existing_identity_mismatch")
    now = at or datetime.now(UTC)
    source = _evidence(item, item["fields"].get("name"))
    values = (
        base.model_dump(mode="json")
        if base
        else {
            "pandal_id": _slug(region.region_id, name, existing),
            "region_id": region.region_id,
            "country_code": region.country_code,
            "admin1": region.admin1 or "",
            "name": name,
            "area": locality,
            "city": locality,
            "featured": False,
            "sources": [],
        }
    )
    values["last_verified_at"] = now.isoformat()
    if str(source.source_url) not in {s["source_url"] for s in values["sources"]}:
        values["sources"].append(source.model_dump(mode="json"))
    if _field(item, "organizer"):
        values["organizer"] = _field(item, "organizer")
    about = item.get("summaries", {}).get("about", [])
    if about:
        values["about"] = SourcedText(
            text=about[0]["text"],
            evidence=[_evidence(item, s) for s in about[0]["support"]],
        ).model_dump(mode="json")
    if item["source_type"] in {"organizer", "association", "event"}:
        links = values.get("official_links", [])
        if canonical(item["source_url"]) not in {canonical(link["url"]) for link in links}:
            links.append(
                OfficialLink(kind="website", url=item["source_url"], evidence=source).model_dump(
                    mode="json"
                )
            )
        values["official_links"] = links
    if tier == "current_edition_reviewed":
        year = _field(item, "year")
        if not year or not year.isdigit() or int(year) != now.year:
            raise ValueError("current_year_evidence_required")
        timezone = _field(item, "timezone") or region.timezone
        if not timezone:
            raise ValueError("region_timezone_required")
        start = _date(_field(item, "start_date"))
        end = _date(_field(item, "end_date"))
        venue, address = _field(item, "venue"), _field(item, "address")
        location = None
        if venue and address:
            evidence = [_evidence(item, item["fields"][key]) for key in ("venue", "address")]
            location = EditionLocation(
                venue=venue, address=address, city=locality, evidence=evidence
            )
        notes = [
            ProgrammeNote(
                title="Programme highlight",
                text=note["text"],
                evidence=[_evidence(item, s) for s in note["support"]],
            )
            for note in item.get("summaries", {}).get("programme", [])[:3]
        ]
        # A new announcement must never reuse an older edition's anchor.
        old = values.get("edition") or {}
        if location and old.get("year") == int(year) and old.get("location"):
            previous = old["location"]
            if norm(previous["venue"]) == norm(venue) and norm(previous["address"]) == norm(
                address
            ):
                location = EditionLocation.model_validate(previous)
        edition = Edition(
            year=int(year),
            confirmed=True,
            start_date=start,
            end_date=end,
            timezone=timezone,
            venue_reviewed=bool(location),
            reviewed_at=now,
            evidence=[
                source,
                *([_evidence(item, item["fields"]["year"])] if _field(item, "year") else []),
            ],
            location=location,
            programme_notes=notes,
        )
        values["edition"] = edition.model_dump(mode="json")
        values["year"] = int(year)
    # Source-listed approval never promotes a new edition. Existing reviewed
    # editions survive a source/profile update without a newer-year assertion.
    record = PandalRecord.model_validate(values)
    monitored = next(
        (
            s
            for s in config.sources
            if s.region_id == region.region_id
            and canonical(str(s.url)) == canonical(item["source_url"])
        ),
        None,
    )
    spec = (
        monitored.model_copy(
            update={
                "reviewed_revision": item.get("monitor_revision") or monitored.reviewed_revision
            }
        )
        if monitored
        else SourceSpec(
            source_id="approved-" + item["candidate_id"],
            url=item["source_url"],
            publisher=urlsplit(item["source_url"]).hostname,
            region_id=region.region_id,
            source_kind=item["source_type"],
            reviewed_revision=item.get("monitor_revision"),
        )
    )
    return {
        "candidate_id": item["candidate_id"],
        "source_revision": item["source_revision"],
        "monitor_revision": spec.reviewed_revision,
        "tier": tier,
        "record": record.model_dump(mode="json"),
        "source": spec.model_dump(mode="json"),
    }


def issue_body(payload):
    return (
        ISSUE_MARKER
        + "\n"
        + json.dumps(payload, ensure_ascii=False, sort_keys=True)
        + "\n"
        + ISSUE_END
    )


def parse_issue_body(body):
    if (
        not isinstance(body, str)
        or not body.startswith(ISSUE_MARKER + "\n")
        or not body.endswith("\n" + ISSUE_END)
    ):
        raise ValueError("invalid_approval_issue")
    if len(body) > 60000:
        raise ValueError("approval_issue_too_large")
    value = json.loads(body[len(ISSUE_MARKER) + 1 : -len(ISSUE_END) - 1])
    if set(value) != {
        "candidate_id",
        "source_revision",
        "monitor_revision",
        "tier",
        "record",
        "source",
    }:
        raise ValueError("approval_fields_invalid")
    if value["tier"] not in {"source_listed", "current_edition_reviewed"}:
        raise ValueError("approval_tier_invalid")
    record = PandalRecord.model_validate(value["record"])
    source = SourceSpec.model_validate(value["source"])
    if (
        source.region_id != record.region_id
        or source.reviewed_revision != value["monitor_revision"]
    ):
        raise ValueError("approval_source_mismatch")
    if not any(
        str(s.source_url) == str(source.url) and s.source_revision_id == value["source_revision"]
        for s in record.sources
    ):
        raise ValueError("approval_evidence_missing")
    if value["tier"] == "current_edition_reviewed" and not (
        record.edition and record.edition.confirmed
    ):
        raise ValueError("approval_edition_missing")
    return value
