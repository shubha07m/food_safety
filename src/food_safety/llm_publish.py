"""Turn fully grounded LLM candidates into ordinary publication candidates.

The model proposes fields; source-grounding and publication validators decide whether
a result can enter the ordinary auto-publish path.
"""

import re
from datetime import date

from bs4 import BeautifulSoup

from . import __version__
from .classify import display_summary
from .documents import freeze_document, mapped_text, resolve_quote
from .models import Event
from .verify import publication_errors


def publishable_drafts(cfg, report, html, url, title, text, policy, policies, at):
    """Return only candidates that pass every objective publication check."""
    if not (cfg.publish_from_llm and report.get("status") == "evaluated"):
        return []
    drafts = []
    for row in report["candidates"]:
        if row["decision"] != "pass":
            row["publication_errors"] = row["validation_errors"]
            continue
        try:
            draft = grounded_event(row, report, html, url, title, text, policy, at)
            errors = publication_errors(draft, policies, {url: text})
            row["publication_errors"] = errors
            if not errors:
                drafts.append(draft)
        except (ValueError, KeyError, TypeError, StopIteration):
            row["publication_errors"] = ["publication_mapping_failed"]
            continue
    return drafts


def grounded_event(row, report, html, url, title, text, policy, at):
    """Map an evidence-validated candidate to the existing public Event model."""
    from .pipeline import candidate

    document = freeze_document(html, url, policy.language)
    if document.source_revision_id != report["source_revision_id"]:
        raise ValueError("revision_changed")
    supported = row["supported_fields"]
    observation = supported["reported_observation"]
    evidence = row["resolved_spans"][observation["evidence_span_ids"][0]]
    passage = next(item for item in document.passages if item.passage_id == evidence["passage_id"])
    proof = {
        **resolve_quote(passage.original_text, evidence["original_quote"]),
        "source_revision_id": document.source_revision_id,
        "passage_id": passage.passage_id,
    }
    if len(proof["original_quote"].split()) > 60:
        raise ValueError("evidence_quote_too_long")
    proposed = {
        "reported_observation": supported["reported_observation"]["raw_value"],
        "reported_action": supported["actions.0"]["raw_value"],
        "reported_authority": supported["reported_authority"]["raw_value"],
        "area": supported["area"]["raw_value"],
    }
    if "establishment_name" in supported:
        proposed["establishment_name"] = supported["establishment_name"]["raw_value"]
    if len(proposed["reported_observation"].split()) > 25:
        raise ValueError("reported_observation_too_long")
    core_names = ["area", "reported_authority", "reported_observation", "actions.0"]
    if row["record_scope"] == "establishment_event":
        core_names.append("establishment_name")
    common_ids = set.intersection(
        *(set(supported[name]["evidence_span_ids"]) for name in core_names)
    )
    required_values = [mapped_text(value, True)[0] for value in proposed.values()]
    contexts = [
        row["resolved_spans"][span_id]["original_quote"]
        for span_id in common_ids
        if all(
            value in mapped_text(row["resolved_spans"][span_id]["original_quote"], True)[0]
            for value in required_values
        )
    ]
    if not contexts:
        raise ValueError("core_evidence_not_co_located")
    evidence_context = min(contexts, key=len)
    if len(evidence_context.split()) > 60:
        raise ValueError("evidence_context_too_long")
    quantity = next(
        (supported[key] for key in sorted(supported) if key.startswith("quantities.")), None
    )
    if (
        quantity
        and mapped_text(quantity["raw_value"], True)[0] in mapped_text(evidence_context, True)[0]
    ):
        proposed["reported_quantity"] = quantity["raw_value"]
    event_date = None
    if "event_date_expression" in supported:
        raw_date = supported["event_date_expression"]["raw_value"]
        if re.fullmatch(r"20\d{2}-\d{2}-\d{2}", raw_date):
            parsed = date.fromisoformat(raw_date)
            if parsed <= at.date():
                event_date = raw_date
                if mapped_text(raw_date, True)[0] in mapped_text(evidence_context, True)[0]:
                    proposed["event_date"] = raw_date
                else:
                    event_date = None
    # The generic candidate helper initially links every field to the observation.
    # LLM candidates replace those links below with their validated shared context.
    draft = candidate(url, title, text, policy, proposed, at, validate_evidence=False)
    data = draft.model_dump(mode="json")
    source = data["sources"][0]
    source_date = _publication_date(html, at)
    source["source_date"] = source_date.isoformat() if source_date else None
    source["evidence_quote"] = proposed["reported_observation"]
    source["evidence_context"] = evidence_context
    source["retrieved_at"] = at.isoformat()
    data["reported_fact"]["event_date"] = event_date
    data["reported_fact"]["legal_finding_status"] = "unknown"
    for field, value in data["reported_fact"].items():
        if field == "evidence" or value is None or field == "legal_finding_status":
            continue
        data["reported_fact"]["evidence"][field] = {
            "source_url": url,
            "quote": evidence_context,
        }
    data["verification_status"] = "SOURCE VERIFIED"
    data["verification_notes"] = (
        "LLM-assisted candidate; objective source-grounding and publication checks passed. "
        "Source verification is not an independent finding of fact."
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
    data["validator_id"] = "objective_source_grounding"
    data["validator_version"] = "2"
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
    event.display_summary = display_summary(event.reported_fact, event.derived_context)
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
    return None
