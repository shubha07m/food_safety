"""Untrusted candidate contract and field decisions; no publication permissions."""

import hashlib
import json
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from .documents import mapped_text, resolve_quote
from .safety import claim_risks, reject_sensitive_fields

TASK_VERSION = "source_candidates_v1"
Short = Annotated[str, StringConstraints(min_length=1, max_length=600)]
Scope = Literal[
    "establishment_event",
    "area_operation",
    "district_operation",
    "statewide_operation",
    "aggregate_report",
]
SpanId = Annotated[str, StringConstraints(pattern=r"^[SP][A-Za-z0-9_-]{1,20}$")]


class CandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class EvidenceProposal(CandidateModel):
    span_id: Annotated[str, StringConstraints(pattern=r"^[SP][A-Za-z0-9_-]{1,20}$")]
    passage_id: Annotated[str, StringConstraints(pattern=r"^P[0-9]{3,5}$")]
    original_quote: Annotated[str, StringConstraints(min_length=1, max_length=1200)]


class SupportedValue(CandidateModel):
    raw_value: Short
    evidence_span_ids: list[SpanId] = Field(min_length=1, max_length=3)


class Quantity(SupportedValue):
    applies_to: Literal["establishment", "operation", "unknown"]


class Relationship(CandidateModel):
    target_candidate_id: Annotated[str, StringConstraints(pattern=r"^C[0-9]{1,3}$")]
    relationship: Literal["part_of_operation", "same_event_as", "supersedes"]
    evidence_span_ids: list[str] = Field(min_length=1, max_length=3)


class CandidateRecord(CandidateModel):
    candidate_id: Annotated[str, StringConstraints(pattern=r"^C[0-9]{1,3}$")]
    record_scope: Scope
    evidence_spans: list[EvidenceProposal] = Field(min_length=1, max_length=16)
    establishment_name: SupportedValue | None
    area: SupportedValue | None
    reported_authority: SupportedValue | None
    reported_observation: SupportedValue
    actions: list[SupportedValue] = Field(max_length=6)
    event_date_expression: SupportedValue | None
    quantities: list[Quantity] = Field(max_length=6)
    relationships: list[Relationship] = Field(max_length=6)


class ExtractionResult(CandidateModel):
    completion_status: Literal["complete", "incomplete", "no_event"]
    candidates: list[CandidateRecord] = Field(max_length=12)


def schema():
    return ExtractionResult.model_json_schema()


def parse_result(payload, max_candidates=12):
    """Validate siblings separately; malformed envelopes never reach field handling."""
    raw = json.loads(payload)
    if not isinstance(raw, dict) or set(raw) != {"completion_status", "candidates"}:
        raise ValueError("invalid_envelope")
    if raw["completion_status"] not in {"complete", "incomplete", "no_event"}:
        raise ValueError("invalid_completion_status")
    rows = raw["candidates"]
    if not isinstance(rows, list) or len(rows) > max_candidates:
        raise ValueError("candidate_limit")
    if raw["completion_status"] == "no_event" and rows:
        raise ValueError("contradictory_no_event")
    accepted, invalid, ids = [], [], set()
    for index, row in enumerate(rows):
        try:
            reject_sensitive_fields(row)
            record = CandidateRecord.model_validate(row)
            if record.candidate_id in ids:
                raise ValueError("duplicate_candidate_id")
            ids.add(record.candidate_id)
            accepted.append(record)
        except (ValueError, ValidationError):
            invalid.append({"index": index, "reason": "candidate_schema_invalid"})
    return raw["completion_status"], accepted, invalid


SEMANTIC_FLAGS = re.compile(
    r"\b(?:not|never|denied|alleged|may|might|planned|correction|corrected|"
    r"withdrawn|retracted|clarification|reportedly)\b|"
    r"অস্বীকার|সংশোধন|প্রত্যাহার|ঘটেনি|অভিযোগ|হয়নি|হয়নি|করেননি|হতে পারে|"
    r"ignore.{0,25}instructions|system prompt",
    re.I,
)


def validate_candidate(record, document, deterministic=()):
    passages = {p.passage_id: p.original_text for p in document.passages}
    spans, reasons, invalid_spans = {}, [], set()
    for span in record.evidence_spans:
        if span.span_id in spans or span.span_id in invalid_spans:
            reasons.append("duplicate_span_id")
            invalid_spans.add(span.span_id)
            spans.pop(span.span_id, None)
            continue
        try:
            resolved = resolve_quote(passages[span.passage_id], span.original_quote)
            spans[span.span_id] = {
                **resolved,
                "passage_id": span.passage_id,
                "source_revision_id": document.source_revision_id,
            }
        except (ValueError, KeyError):
            invalid_spans.add(span.span_id)

    fields, omitted = {}, []

    def support(name, value, optional=False):
        if value is None:
            return
        linked = [spans.get(key) for key in value.evidence_span_ids]
        raw, _ = mapped_text(value.raw_value, True)
        valid = all(linked) and any(
            raw in mapped_text(s["original_quote"], True)[0] for s in linked
        )
        if not valid or claim_risks(value.raw_value):
            (omitted if optional else reasons).append(f"unsupported:{name}")
            return
        fields[name] = value.model_dump()

    for name in ["establishment_name", "area", "reported_authority", "reported_observation"]:
        support(name, getattr(record, name))
    for index, value in enumerate(record.actions):
        support(f"actions.{index}", value)
    support("event_date_expression", record.event_date_expression, optional=True)
    for index, value in enumerate(record.quantities):
        support(f"quantities.{index}", value, optional=True)
        if f"quantities.{index}" in fields and (
            value.applies_to == "unknown"
            or (value.applies_to == "operation" and record.record_scope == "establishment_event")
        ):
            fields.pop(f"quantities.{index}", None)
            reasons.append("quantity_entity_uncertain")
    for required in ["area", "reported_observation", "reported_authority"]:
        if required not in fields:
            reasons.append(f"missing_core:{required}")
    if not record.actions:
        reasons.append("missing_core:action")
    if record.record_scope == "establishment_event" and "establishment_name" not in fields:
        reasons.append("missing_core:establishment")
    # Inspect full cited paragraphs, not just the model-selected positive fragment.
    cited = "\n".join(passages[s["passage_id"]] for s in spans.values())
    if SEMANTIC_FLAGS.search(cited) or claim_risks(cited):
        reasons.append("semantic_context_review")
    if re.search(
        r"\b(?:correction|corrected|withdrawn|retracted|clarification)\b|সংশোধন|প্রত্যাহার",
        "\n".join(passages.values()),
        re.I,
    ):
        reasons.append("document_correction_requires_review")
    if record.event_date_expression is not None:
        omitted.append("event_date_expression_requires_normalization")
    if record.relationships:
        reasons.append("relationship_requires_review")
        if any(key not in spans for r in record.relationships for key in r.evidence_span_ids):
            reasons.append("unsupported:relationship_evidence")
    required = ["area", "reported_authority", "reported_observation"]
    if record.record_scope == "establishment_event":
        required.append("establishment_name")
    core_values = [fields[name]["raw_value"] for name in required if name in fields]
    core_values.extend(value.raw_value for value in record.actions)
    relation_spans = [
        span
        for span in spans.values()
        if all(
            mapped_text(value, True)[0] in mapped_text(span["original_quote"], True)[0]
            for value in core_values
        )
    ]
    if not relation_spans:
        reasons.append("entity_action_relationship_requires_review")
    if any(name.startswith("quantities.") for name in fields):
        reasons.append("quantity_association_requires_review")
    key = hashlib.sha256(
        json.dumps(
            {"scope": record.record_scope, "fields": fields},
            sort_keys=True,
        ).encode()
    ).hexdigest()
    duplicate = any(
        scope == record.record_scope
        and values.get("reported_observation") == record.reported_observation.raw_value
        and values.get("establishment_name")
        == (record.establishment_name.raw_value if record.establishment_name else None)
        for _, values, scope in deterministic
    )
    rejected = any(
        reason.startswith(("unsupported:", "missing_core:", "duplicate_span")) for reason in reasons
    )
    return {
        "candidate_id": record.candidate_id,
        "candidate_key": key,
        "record_scope": record.record_scope,
        "supported_fields": fields,
        "resolved_spans": spans,
        "omitted_fields": omitted,
        "review_reasons": sorted(set(reasons)),
        "decision": "reject" if rejected else ("review" if reasons else "pass"),
        "duplicate_of_deterministic": duplicate,
        "relationship_suggestions": [r.model_dump() for r in record.relationships],
        "publication_eligible": not reasons,
    }
