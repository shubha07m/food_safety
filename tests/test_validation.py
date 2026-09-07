from food_safety.extract import article_text
from food_safety.models import Event
from food_safety.verify import evidence_errors, publication_errors


def test_valid_evidence(record, policy, fixture_html):
    _, text = article_text(fixture_html)
    assert not publication_errors(record, [policy], {record.sources[0].source_url: text}, True)


def test_missing_evidence(record):
    record.reported_fact.evidence.pop("reported_action")
    assert "missing_evidence:reported_action" in evidence_errors(record)


def test_unsupported_claim(record):
    record.reported_fact.reported_action = "Notice issued."
    assert "value_not_in_span:reported_action" in evidence_errors(record)


def test_source_changed(record):
    assert "source_changed" in evidence_errors(record, {record.sources[0].source_url: "changed"})


def test_source_unreachable(record):
    assert "source_unreachable" in evidence_errors(record, {})


def test_fixture_blocked(record, policy):
    assert "fixture_not_public" in publication_errors(record, [policy])


def test_review_required(record, policy):
    record.review = None
    assert "human_context_review_required" in publication_errors(record, [policy])


def test_derived_needs_support(record, policy):
    record.derived_context.derived_menu_category = "both"
    assert "unsupported_derived_context" in publication_errors(record, [policy])


def test_weak_source(record, policy):
    record.sources[0].tier = "C"
    assert "insufficient_source_tier" in publication_errors(record, [policy])


def test_cross_source_requires_independence(record, policy):
    data = record.model_dump(mode="json")
    data["verification_status"] = "CROSS-SOURCE VERIFIED"
    data["history"][-1]["status"] = "CROSS-SOURCE VERIFIED"
    assert "independent_sources_required" in publication_errors(
        Event.model_validate(data), [policy]
    )


def test_formal_finding_requires_authority(record):
    record.reported_fact.formal_finding = "Finding"
    record.sources[0].tier = "B"
    assert "formal_finding_requires_authority" in evidence_errors(record)
