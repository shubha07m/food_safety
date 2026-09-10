"""Policy gate: model proposals never carry publication authority.

Eligible candidates must be independently reconstructible by the current narrow
semantic grammar. Increasing that grammar's coverage needs tests, not a trust score.
"""

from . import __version__
from .automatic import automatic_matches, prepare_automatic
from .documents import freeze_document, mapped_text, resolve_quote
from .models import Event
from .storage import dump
from .verify import publication_errors


def guarded_drafts(root, cfg, report, html, url, title, text, policy, policies, at):
    if not (
        cfg.llm_mode == "guarded"
        and cfg.publish_from_llm
        and report.get("status") == "evaluated"
        and report.get("publication_eligible")
    ):
        return []
    drafts, decisions = [], []
    for row in report["candidates"]:
        decision = {
            "candidate_id": row["candidate_id"],
            "decision": row["decision"],
            "reasons": row["review_reasons"],
        }
        decisions.append(decision)
        if row["decision"] != "pass":
            continue
        try:
            draft = grounded_event(row, report, html, url, title, text, policy, at)
            errors = publication_errors(draft, policies, {url: text})
            if errors:
                decision.update(decision="reject", reasons=errors)
            else:
                drafts.append(draft)
        except (ValueError, KeyError, TypeError, StopIteration):
            decision.update(decision="review", reasons=["publication_grounding_not_established"])
    # Structured exceptions remain private and never masquerade as reviewed Event objects.
    queue_name = f"{report['source_id']}-{report['source_revision_id']}.json"
    dump(
        root / ".cache/llm_eval/queue" / queue_name,
        {
            "source_id": report["source_id"],
            "source_revision_id": report["source_revision_id"],
            "decisions": decisions,
            "candidates": report["candidates"],
        },
    )
    return drafts


def grounded_event(row, report, html, url, title, text, policy, at):
    from .pipeline import candidate

    document = freeze_document(html, url, policy.language)
    if document.source_revision_id != report["source_revision_id"]:
        raise ValueError("revision_changed")
    proposed = {k: v["raw_value"] for k, v in row["supported_fields"].items()}
    proposed["reported_action"] = proposed.pop("actions.0")
    # The grammar, not the model, proves scope and entity/action associations.
    selected = next(
        match
        for match in automatic_matches(text)
        if match[2] == row["record_scope"]
        and set(match[1]) == set(proposed)
        and all(
            mapped_text(match[1][k], True)[0] == mapped_text(v, True)[0]
            for k, v in proposed.items()
        )
    )
    observation = row["supported_fields"]["reported_observation"]
    observation_span = row["resolved_spans"][observation["evidence_span_ids"][0]]
    passage = next(p for p in document.passages if p.passage_id == observation_span["passage_id"])
    resolved = resolve_quote(passage.original_text, selected[1]["reported_observation"])
    proof = {
        **resolved,
        "source_revision_id": document.source_revision_id,
        "passage_id": passage.passage_id,
    }
    draft = candidate(url, title, text, policy, selected[1], at)
    draft = prepare_automatic(draft, html, text, at, selected)
    if draft is None:
        raise ValueError("automatic_context_or_date_not_proven")
    data = draft.model_dump(mode="json")
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
    data["automatic_validation"].update(
        method="source_grounded_candidate_v1",
        extraction_evidence=proof,
    )
    data["extractor_id"] = "source_grounded_candidate"
    data["extractor_version"] = "1"
    data["verification_notes"] = (
        "LLM-assisted candidate; independent deterministic source, relationship and publication "
        "checks passed. No human review is claimed. Publication date is not an event date."
    )
    return Event.model_validate(data)
