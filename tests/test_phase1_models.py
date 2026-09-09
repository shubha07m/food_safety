import hashlib

import pytest
from conftest import AT

from food_safety.models import ComplianceDocument, Source
from food_safety.verify import publication_errors


def document_payload(record):
    quote = (
        "Example Kitchen in Example Area. Example Authority issued a licence "
        "on 2026-01-02 for food service. Status: issued."
    )
    source = record.sources[0].model_dump(mode="json")
    source.update(
        evidence_quote=quote,
        evidence_context=quote,
        evidence_span_hash="",
        source_revision_id="",
        text_sha256=hashlib.sha256(quote.encode()).hexdigest(),
    )
    facts = dict(
        establishment_name="Example Kitchen",
        area="Example Area",
        issuer="Example Authority",
        document_date="2026-01-02",
        scope="food service",
        document_status_as_reported="issued",
    )
    return dict(
        record_id="BFPC-aaaaaaaaaaaa",
        evidence_type="licence",
        **facts,
        source=source,
        publication_status="active",
        reviewed_at=AT,
        issuer_check_status="source_checked",
        supported_fields={k: {"source_url": source["source_url"], "quote": quote} for k in facts},
    )


def test_compliance_url_only_reviewed(record):
    assert (
        ComplianceDocument.model_validate(document_payload(record)).record_class
        == "licensing_compliance_document"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("reviewed_at", None),
        ("issuer_check_status", "not_checked"),
        ("evidence_type", "award"),
        ("upload", "file.pdf"),
        ("submitter_email", "private@example.org"),
    ],
)
def test_compliance_rejects_unsafe_or_unreviewed(record, field, value):
    data = document_payload(record)
    data[field] = value
    with pytest.raises(ValueError):
        ComplianceDocument.model_validate(data)


def test_compliance_missing_field_evidence(record):
    data = document_payload(record)
    data["supported_fields"].pop("scope")
    with pytest.raises(ValueError, match="unsupported_document_field"):
        ComplianceDocument.model_validate(data)


def test_tampered_source_digest_rejected(record):
    data = record.sources[0].model_dump(mode="json")
    data["evidence_span_hash"] = "a" * 64
    with pytest.raises(ValueError, match="source_provenance_mismatch"):
        Source.model_validate(data)


def test_cross_source_requires_reviewed_independence(record, policy):
    data = record.model_dump(mode="json")
    data["verification_status"] = "CROSS-SOURCE VERIFIED"
    data["history"][-1]["status"] = "CROSS-SOURCE VERIFIED"
    from food_safety.models import Event

    event = Event.model_validate(data)
    assert "source_independence_review_required" in publication_errors(event, [policy])
