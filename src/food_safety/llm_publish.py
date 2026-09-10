"""Turn fully grounded LLM candidates into ordinary publication candidates.

The model proposes fields; source-grounding and publication validators decide whether
a result can enter the ordinary auto-publish path.
"""

import re
from datetime import date

from bs4 import BeautifulSoup

from . import __version__
from .classify import display_summary
from .documents import freeze_document, resolve_quote
from .models import Event
from .storage import dump
from .verify import publication_errors


def publishable_drafts(root, cfg, report, html, url, title, text, policy, policies, at):
    """Return clean records and save only exception metadata to the private queue."""
    if not (cfg.publish_from_llm and report.get("status") == "evaluated"):
        return []
    drafts, exceptions = [], []
    for row in report["candidates"]:
        if row["decision"] != "pass":
            exceptions.append(_exception(row, row["decision"], row["review_reasons"]))
            continue
        try:
            draft = grounded_event(row, report, html, url, title, text, policy, at)
            errors = publication_errors(draft, policies, {url: text})
            if errors:
                exceptions.append(_exception(row, "reject", errors))
            else:
                drafts.append(draft)
        except (ValueError, KeyError, TypeError, StopIteration):
            exceptions.append(_exception(row, "review", ["publication_grounding_not_established"]))
    if exceptions:
        # Candidate bodies can include source text. This ignored local queue holds
        # only compact exception metadata and never blocks clean candidates.
        queue_name = f"{report['source_id']}-{report['source_revision_id']}.json"
        dump(
            root / ".cache/llm/queue" / queue_name,
            {
                "source_id": report["source_id"],
                "source_revision_id": report["source_revision_id"],
                "at": report["at"],
                "exceptions": exceptions,
            },
        )
    return drafts


def _exception(row, decision, reasons):
    return {
        "candidate_id": row["candidate_id"],
        "record_scope": row["record_scope"],
        "decision": decision,
        "reasons": reasons,
    }


def grounded_event(row, report, html, url, title, text, policy, at):
    """Map an evidence-validated candidate to the existing public Event model."""
    from .pipeline import candidate

    document = freeze_document(html, url, policy.language)
    if document.source_revision_id != report["source_revision_id"]:
        raise ValueError("revision_changed")
    proposed = {key: value["raw_value"] for key, value in row["supported_fields"].items()}
    proposed["reported_action"] = proposed.pop("actions.0")
    observation = row["supported_fields"]["reported_observation"]
    evidence = row["resolved_spans"][observation["evidence_span_ids"][0]]
    passage = next(item for item in document.passages if item.passage_id == evidence["passage_id"])
    proof = {
        **resolve_quote(passage.original_text, proposed["reported_observation"]),
        "source_revision_id": document.source_revision_id,
        "passage_id": passage.passage_id,
    }
    if len(proof["original_quote"].split()) > 60:
        raise ValueError("evidence_quote_too_long")
    draft = candidate(url, title, text, policy, proposed, at)
    data = draft.model_dump(mode="json")
    source = data["sources"][0]
    source["source_date"] = _publication_date(html, at).isoformat()
    source["evidence_quote"] = proof["original_quote"]
    source["evidence_context"] = proof["original_quote"]
    source["retrieved_at"] = at.isoformat()
    data["reported_fact"]["event_date"] = None
    data["reported_fact"]["legal_finding_status"] = "none_reported"
    data["verification_status"] = "SOURCE VERIFIED"
    data["verification_notes"] = (
        "LLM-assisted candidate; deterministic source, evidence, relationship and "
        "publication checks passed. Source verification is not an independent finding of fact."
    )
    data["publication_status"] = "active"
    data["evidence_support_status"] = "supported_as_of"
    data["source_availability"] = "available"
    data["source_availability_reason"] = None
    data["last_source_checked_at"] = at.isoformat()
    data["last_successful_evidence_check_at"] = at.isoformat()
    data["first_published_at"] = at.isoformat()
    data["record_scope"] = row["record_scope"]
    data["extractor_id"] = "source_grounded_candidate"
    data["extractor_version"] = "1"
    data["validator_id"] = "field_grounding_and_explicit_relationships"
    data["validator_version"] = "1"
    data["llm"] = {
        "llm_used": True,
        "llm_provider": report["provider"],
        "llm_model": report["usage"]["model_version"],
        "llm_task": "structured source extraction",
        "llm_pipeline_version": __version__,
        "llm_output_was_validated": True,
        "llm_task_version": report["task_version"],
        "llm_used_at": report["model_called_at"],
        "source_revision_id": document.source_revision_id,
        "fields_proposed": sorted(proposed),
        "validation_result": "passed",
    }
    data["automatic_validation"] = {
        "method": "source_grounded_candidate_v1",
        "validated_at": at.isoformat(),
        "pipeline_version": __version__,
        "extraction_evidence": proof,
    }
    data["history"] = [
        {
            "at": at.isoformat(),
            "status": "SOURCE VERIFIED",
            "note": "Source-grounded LLM candidate auto-published after deterministic validation.",
        }
    ]
    event = Event.model_validate(data)
    event.display_summary = display_summary(event)
    return event


def _publication_date(html, fallback):
    soup = BeautifulSoup(html, "html.parser")
    values = [
        tag.get("content", "")
        for tag in soup.select(
            "meta[property='article:published_time'], meta[name='datePublished']"
        )
    ]
    values.extend(re.findall(r'"datePublished"\s*:\s*"([^\"]+)"', html))
    for value in values:
        match = re.search(r"(20\d{2}-\d{2}-\d{2})", value)
        if match:
            parsed = date.fromisoformat(match.group(1))
            if parsed <= fallback.date():
                return parsed
    return fallback.date()
