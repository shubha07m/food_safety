import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from html import escape
from urllib.parse import urlsplit

from . import CONTEXT, SCHEMA_VERSION, __version__
from .config import settings, sources
from .models import ComplianceDocument, Dataset
from .storage import dump, read_events, read_rejected
from .verify import evidence_errors, publication_errors

POLICIES = [
    "DISCLAIMER",
    "METHODOLOGY",
    "CORRECTIONS",
    "PRIVACY",
    "SOURCES",
    "DATA_DICTIONARY",
    "CONTRIBUTING",
]


def policy_html(text):
    """Small escaped Markdown subset; policy source is repository-authored, never scraped."""
    blocks = []
    for paragraph in text.split("\n\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if paragraph.startswith("# "):
            continue
        if paragraph.startswith("## "):
            blocks.append(f"<h2>{escape(paragraph[3:])}</h2>")
        elif paragraph.startswith("https://") and "\n" not in paragraph:
            from .safety import safe_url

            url = safe_url(paragraph)
            blocks.append(
                f'<p><a href="{escape(url, quote=True)}" '
                f'rel="noopener noreferrer">{escape(url)}</a></p>'
            )
        elif paragraph.startswith("| "):
            rows = paragraph.splitlines()
            body = []
            for index, row in enumerate(rows):
                if index == 1:
                    continue
                tag = "th" if index == 0 else "td"
                cells = "".join(
                    f"<{tag}>{escape(cell.strip())}</{tag}>" for cell in row.strip("|").split("|")
                )
                body.append(f"<tr>{cells}</tr>")
            blocks.append('<div class="table-scroll"><table>' + "".join(body) + "</table></div>")
        else:
            blocks.append("<p>" + escape(paragraph).replace("\n", "<br>") + "</p>")
    return "\n".join(blocks)


def validate(root):
    if (root / "data/.transaction.json").exists():
        raise ValueError("unfinished_data_transaction")
    cfg, policies = settings(root), sources(root)
    documents = root / "data/compliance.json"
    if documents.exists():
        raw = json.loads(documents.read_text())
        if raw["record_count"] != len(raw["records"]):
            raise ValueError("document_count_mismatch")
        for row in raw["records"]:
            document = ComplianceDocument.model_validate(row)
            if document.publication_status != "active":
                raise ValueError("only_reviewed_active_documents_exported")
            if not any(
                p.enabled
                and p.domain == urlsplit(document.source.source_url).hostname
                and p.tier == document.source.tier
                for p in policies
            ):
                raise ValueError("document_source_not_permitted")
    events, pending = read_events(root, "events"), read_events(root, "pending")
    ids = [e.event_id for e in [*events, *pending]]
    if len(ids) != len(set(ids)):
        raise ValueError("event_in_multiple_queues")
    source_quotes = defaultdict(set)
    for event in events:
        errors = publication_errors(event, policies)
        if errors:
            raise ValueError(event.event_id + ": " + ", ".join(errors))
        for source in event.sources:
            source_quotes[source.source_url].add(source.evidence_context)
    for spans in source_quotes.values():
        # The copyright budget applies across the dataset, not just to individual records.
        maximal = [span for span in spans if not any(span != s and span in s for s in spans)]
        if sum(len(s.split()) for s in maximal) > 250:
            raise ValueError("dataset_source_quote_budget_exceeded")
    for event in pending:
        if evidence_errors(event):
            raise ValueError(event.event_id + ": invalid pending evidence")
    rejected = read_rejected(root)
    if set(rejected) != {
        "generated_at",
        "schema_version",
        "pipeline_version",
        "record_count",
        "context_notice",
        "records",
    }:
        raise ValueError("invalid_rejected_envelope")
    Dataset.model_validate({**rejected, "records": [], "record_count": 0})
    if rejected["record_count"] != len(rejected["records"]):
        raise ValueError("rejected_count_mismatch")
    for row in rejected["records"]:
        if (
            set(row) != {"candidate_id", "at", "reason"}
            or row["reason"] not in {"candidate_rejected", "fetch_failed", "maintainer_rejected"}
            or not re.fullmatch(r"[a-f0-9]{16}", row["candidate_id"])
        ):
            raise ValueError("invalid_rejection_tombstone")
    schema = json.loads((root / "data/schema_version.json").read_text())
    if schema != {"schema_version": SCHEMA_VERSION, "pipeline_version": __version__}:
        raise ValueError("schema_version_mismatch")
    return {"published": len(events), "pending": len(pending), "repository_url": cfg.repository_url}


def aggregates(records):
    def count(fn):
        return dict(sorted(Counter(fn(r) for r in records).items()))

    return {
        "total": len(records),
        "areas_count": len({r.reported_fact.area for r in records if r.reported_fact.area}),
        "establishments_count": len(
            {
                r.reported_fact.establishment_name
                for r in records
                if r.reported_fact.establishment_name
            }
        ),
        "sources_count": len({s.source_url for r in records for s in r.sources}),
        "timeline": count(
            lambda r: str(
                r.reported_fact.event_date
                or next((s.source_date for s in r.sources if s.source_date), "Unknown")
            )
        ),
        "areas": count(lambda r: r.reported_fact.area or "Unknown"),
        "actions": count(lambda r: r.derived_context.action_category),
        "establishments": count(lambda r: r.derived_context.establishment_context),
        "menus": count(lambda r: r.derived_context.menu_context),
        "business_formats": count(lambda r: r.derived_context.business_format),
        "publishers": count(lambda r: r.sources[0].source_publisher),
        "verification": count(lambda r: r.verification_status),
        "map_coverage": {
            "mapped_records": sum(
                r.derived_context.latitude is not None and r.derived_context.longitude is not None
                for r in records
            ),
            "precision": count(lambda r: r.derived_context.location_precision or "not mapped"),
        },
        "coverage": {
            "named_establishment": sum(bool(r.reported_fact.establishment_name) for r in records),
            "reported_action": sum(bool(r.reported_fact.reported_action) for r in records),
            "reported_quantity": sum(bool(r.reported_fact.reported_quantity) for r in records),
            "establishment_context": sum(
                r.derived_context.establishment_context != "unknown" for r in records
            ),
            "menu_context": sum(r.derived_context.menu_context != "unknown" for r in records),
            "business_format": sum(r.derived_context.business_format != "unknown" for r in records),
            "cross_source": sum(r.verification_status == "CROSS-SOURCE VERIFIED" for r in records),
        },
    }


def csv_text(records, generated_at=""):
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "event_id",
            "event_date",
            "area",
            "establishment_name",
            "reported_observation",
            "reported_action",
            "reported_quantity",
            "reported_authority",
            "display_summary",
            "action_category",
            "establishment_context",
            "menu_context",
            "business_format",
            "latitude",
            "longitude",
            "location_precision",
            "source_urls",
            "verification_status",
            "context_notice",
            "generated_at",
            "schema_version",
            "pipeline_version",
            "record_count",
            "publication_status",
            "source_availability",
            "source_availability_reason",
            "evidence_support_status",
            "last_successful_evidence_check_at",
            "first_published_at",
        ]
    )
    for record in records:
        facts = record.reported_fact
        values = [
            record.event_id,
            facts.event_date,
            facts.area,
            facts.establishment_name,
            facts.reported_observation,
            facts.reported_action,
            facts.reported_quantity,
            facts.reported_authority,
            record.display_summary,
            record.derived_context.action_category,
            record.derived_context.establishment_context,
            record.derived_context.menu_context,
            record.derived_context.business_format,
            record.derived_context.latitude,
            record.derived_context.longitude,
            record.derived_context.location_precision,
            " | ".join(s.source_url for s in record.sources),
            record.verification_status,
            CONTEXT,
            generated_at,
            SCHEMA_VERSION,
            __version__,
            len(records),
            record.publication_status,
            record.source_availability,
            record.source_availability_reason,
            record.evidence_support_status,
            record.last_successful_evidence_check_at,
            record.first_published_at,
        ]
        # Prevent spreadsheet formulas, including leading whitespace/control characters.
        writer.writerow(
            [
                (
                    "'" + str(v)
                    if str(v or "").lstrip().startswith(("=", "+", "-", "@"))
                    else str(v or "")
                )
                for v in values
            ]
        )
    return output.getvalue()


def lifecycle_counts(records, retired, at):
    active_ids = {r.event_id for r in records}
    inactive = {r["event_id"]: r for r in retired if r["event_id"] not in active_ids}
    states = Counter(r.publication_status for r in records)
    states.update(r.get("publication_status", "needs_review") for r in inactive.values())
    first = {r.event_id: r.first_published_at for r in records}
    for key, row in inactive.items():
        first[key] = (
            datetime.fromisoformat(row["first_published_at"])
            if row.get("first_published_at")
            else None
        )
    clock = datetime.fromisoformat(at)
    return {
        "as_of": at,
        "active": len(active_ids),
        "ever_published": len(active_ids | set(inactive)),
        "non_active": len(inactive),
        "states": dict(sorted(states.items())),
        "new_last_7_days": sum(
            value is not None and clock - timedelta(days=7) <= value <= clock
            for value in first.values()
        ),
        "unknown_first_publication": sum(value is None for value in first.values()),
        "context_notice": CONTEXT,
    }


def build(root):
    counts = validate(root)
    site = root / "site"
    site.mkdir(exist_ok=True)
    public = json.loads((root / "data/events.json").read_text())
    records = read_events(root, "events")
    dump(site / "data/events.json", public)
    dump(
        site / "data/aggregates.json",
        {
            **{
                k: public[k]
                for k in (
                    "generated_at",
                    "schema_version",
                    "pipeline_version",
                    "record_count",
                    "context_notice",
                )
            },
            **aggregates(records),
        },
    )
    export = csv_text(records, public["generated_at"])
    (root / "data/events.csv").write_text(export)
    (site / "data/events.csv").write_text(export)
    metadata = {key: value for key, value in public.items() if key != "records"}
    dump(root / "data/events.csv.metadata.json", metadata)
    dump(site / "data/events.csv.metadata.json", metadata)
    status = json.loads((root / "data/status.json").read_text())
    dump(
        site / "status.json",
        {
            **status,
            "published_count": counts["published"],
            "held_from_last_scan": status.get("held_from_last_scan", 0),
        },
    )
    dump(
        site / "repository.json",
        {
            "url": counts["repository_url"],
            "site_url": settings(root).site_url,
            "community_submission_url": settings(root).community_submission_url,
        },
    )
    mapped = [
        {
            "event_id": r.event_id,
            "area": r.derived_context.normalized_area or r.reported_fact.area,
            "latitude": r.derived_context.latitude,
            "longitude": r.derived_context.longitude,
            "location_precision": r.derived_context.location_precision,
            "location_source": r.derived_context.location_source,
        }
        for r in records
        if r.derived_context.latitude is not None and r.derived_context.longitude is not None
    ]
    dump(site / "data/locations.json", {"record_count": len(mapped), "records": mapped})
    # Never deploy pending/rejected content or private record snapshots.
    retired = [
        {
            "event_id": r.event_id,
            "verification_status": r.verification_status,
            "record_updated_at": r.record_updated_at.isoformat(),
            "publication_status": r.publication_status,
            "superseded_by": r.superseded_by,
            "first_published_at": r.first_published_at.isoformat()
            if r.first_published_at
            else None,
            "source_availability_reason": r.source_availability_reason,
            "context_notice": CONTEXT,
            "source_url_sha256": [
                hashlib.sha256(s.source_url.encode()).hexdigest() for s in r.sources
            ],
        }
        for r in read_events(root, "pending")
        if any(h.status in {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"} for h in r.history)
    ]
    retired_path = root / "data/retired.json"
    previous = json.loads(retired_path.read_text())["records"] if retired_path.exists() else []
    by_id = {r["event_id"]: r for r in [*previous, *retired]}
    for record in records:
        by_id.pop(record.event_id, None)
    retired = list(by_id.values())
    retirement_data = {**metadata, "record_count": len(retired), "records": retired}
    dump(retired_path, retirement_data)
    dump(site / "data/retired.json", retirement_data)
    dump(
        site / "data/lifecycle.json",
        lifecycle_counts(records, retired, status.get("last_attempt") or public["generated_at"]),
    )
    document_path = root / "data/compliance.json"
    if document_path.exists():
        dump(site / "data/compliance.json", json.loads(document_path.read_text()))
    for name in POLICIES:
        text = (root / f"{name}.md").read_text()
        target = site / "policies" / f"{name.lower()}.html"
        target.parent.mkdir(exist_ok=True)
        title = name.replace("_", " ").title()
        target.write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{title} · WB Food Safety Evidence Tracker</title>"
            '<link rel="stylesheet" href="../styles.css">'
            '<script type="module" src="../pages.js"></script></head><body>'
            '<a class="skip-link" href="#content">Skip to content</a>'
            '<div class="status-strip">Independent public-source research tracker · '
            "Not a government database · Inclusion is not a finding of wrongdoing</div>"
            '<nav class="policy-nav" aria-label="Main"><a href="../index.html">Tracker</a> '
            '<a href="methodology.html">Methodology</a> <a href="disclaimer.html">Disclaimer</a> '
            '<a href="../corrections.html">Corrections</a> <a href="../data.html">Data</a> '
            '<a href="../corrections.html#github">GitHub</a></nav>'
            f'<main id="content" class="policy"><h1>{title}</h1>'
            '<p class="notice">Project policy draft, not legal advice. India-qualified counsel '
            "should review the wording before broad public promotion. Independent legal review "
            "has not been completed.</p>"
            f'<div class="policy-copy">{policy_html(text)}</div></main></body></html>\n'
        )
    return counts
