import csv
import io
import json
import re
from collections import Counter, defaultdict
from html import escape

from . import CONTEXT, SCHEMA_VERSION, __version__
from .config import settings, sources
from .models import Dataset
from .storage import dump, read_events
from .verify import evidence_errors, publication_errors

POLICIES = ["DISCLAIMER", "METHODOLOGY", "CORRECTIONS", "PRIVACY", "SOURCES", "DATA_DICTIONARY"]


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
    rejected = json.loads((root / "data/rejected.json").read_text())
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
            "precision": count(
                lambda r: r.derived_context.location_precision or "not mapped"
            ),
        },
        "coverage": {
            "named_establishment": sum(bool(r.reported_fact.establishment_name) for r in records),
            "reported_action": sum(bool(r.reported_fact.reported_action) for r in records),
            "reported_quantity": sum(bool(r.reported_fact.reported_quantity) for r in records),
            "establishment_context": sum(
                r.derived_context.establishment_context != "unknown" for r in records
            ),
            "menu_context": sum(r.derived_context.menu_context != "unknown" for r in records),
            "business_format": sum(
                r.derived_context.business_format != "unknown" for r in records
            ),
            "cross_source": sum(
                r.verification_status == "CROSS-SOURCE VERIFIED" for r in records
            ),
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
        {**status, "published_count": counts["published"], "pending_count": counts["pending"]},
    )
    dump(site / "repository.json", {"url": counts["repository_url"]})
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
            "context_notice": CONTEXT,
        }
        for r in read_events(root, "pending")
        if any(h.status in {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"} for h in r.history)
    ]
    dump(site / "data/retired.json", {**public, "record_count": len(retired), "records": retired})
    for name in POLICIES:
        text = (root / f"{name}.md").read_text()
        target = site / "policies" / f"{name.lower()}.html"
        target.parent.mkdir(exist_ok=True)
        title = name.replace("_", " ").title()
        target.write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{title} · WB Food Safety Evidence Tracker</title>"
            '<link rel="stylesheet" href="../styles.css"></head><body>'
            '<a class="skip-link" href="#content">Skip to content</a>'
            '<div class="status-strip">Independent public-source research tracker · '
            "Not a government database · Inclusion is not a finding of wrongdoing</div>"
            '<nav class="policy-nav" aria-label="Main"><a href="../index.html">Tracker</a> '
            '<a href="methodology.html">Methodology</a> <a href="disclaimer.html">Disclaimer</a> '
            '<a href="../corrections.html">Corrections</a> <a href="../data.html">Data</a> '
            '<a href="../corrections.html#github">GitHub</a></nav>'
            f'<main id="content" class="policy"><h1>{title}</h1>'
            '<p class="notice">Project policy draft, not legal advice. India-qualified counsel '
            "should review the final wording before broad public launch.</p>"
            f'<div class="policy-copy">{policy_html(text)}</div></main></body></html>\n'
        )
    return counts
