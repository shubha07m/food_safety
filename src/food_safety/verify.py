from collections import defaultdict

from .classify import display_summary
from .extract import text_hash
from .safety import claim_risks, normalize

PUBLIC_STATUSES = {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"}


def evidence_errors(event, texts=None):
    errors = []
    sources = {source.source_url: source for source in event.sources}
    facts = event.reported_fact.model_dump(mode="json", exclude={"evidence"})
    quotes = defaultdict(set)
    for field, support in event.reported_fact.evidence.items():
        if field not in facts or facts[field] is None:
            errors.append("extraneous_field_evidence")
        source = sources.get(support.source_url)
        if not source:
            errors.append("unlinked_evidence")
            continue
        if support.quote not in source.evidence_context:
            errors.append("span_outside_context")
        quotes[source.source_url].add(support.quote)
    for field, value in facts.items():
        if value is None or (field == "legal_finding_status" and value == "unknown"):
            continue
        if field == "legal_finding_status":
            if value != "official_finding_reported" or not event.reported_fact.formal_finding:
                errors.append("legal_finding_requires_official_evidence")
            continue
        support = event.reported_fact.evidence.get(field)
        if support is None:
            errors.append(f"missing_evidence:{field}")
        elif normalize(str(value)) not in normalize(support.quote):
            errors.append(f"value_not_in_span:{field}")
        if claim_risks(str(value)):
            errors.append("claim_safety_review_required")
    if event.reported_fact.formal_finding:
        support = event.reported_fact.evidence.get("formal_finding")
        official = sources.get(support.source_url) if support else None
        if not official or official.tier != "A" or official.source_type != "official":
            errors.append("formal_finding_requires_authority")
    for source in sources.values():
        quotes[source.source_url].update([source.evidence_quote, source.evidence_context])
        # Count distinct stored spans conservatively, without retaining entire articles.
        longest = max(quotes[source.source_url], key=len)
        extra = [q for q in quotes[source.source_url] if q not in longest]
        if sum(len(q.split()) for q in [longest, *extra]) > 60:
            errors.append("quote_budget_exceeded")
        if source.evidence_quote not in source.evidence_context:
            errors.append("quote_outside_context")
        if claim_risks(source.evidence_context) or claim_risks(source.source_title):
            errors.append("claim_safety_review_required")
        if texts is not None:
            text = texts.get(source.source_url)
            if not text:
                errors.append("source_unreachable")
            elif text_hash(text) != source.text_sha256:
                errors.append("source_changed")
            elif source.evidence_context not in text:
                errors.append("evidence_not_in_article")
    return sorted(set(errors))


def publication_errors(event, policies, texts=None, allow_fixtures=False):
    errors = evidence_errors(event, texts)
    if event.is_fixture and not allow_fixtures:
        errors.append("fixture_not_public")
    if event.verification_status not in PUBLIC_STATUSES:
        errors.append("non_public_status")
    review = event.review
    if not review or not review.all_fields_supported or not review.source_context_checked:
        errors.append("human_context_review_required")
    # A source publication date is acceptable when the article does not identify
    # the calendar date of the reported event. The UI labels that distinction.
    has_date = event.reported_fact.event_date or any(s.source_date for s in event.sources)
    if not has_date or not event.reported_fact.area:
        errors.append("date_and_location_review_required")
    from urllib.parse import urlsplit

    for source in event.sources:
        policy = next(
            (p for p in policies if p.domain == urlsplit(source.source_url).hostname), None
        )
        if not policy or not policy.enabled or policy.tier != source.tier:
            errors.append("unapproved_source")
        if source.tier not in {"A", "B"}:
            errors.append("insufficient_source_tier")
        if source.source_type != ("official" if source.tier == "A" else "news"):
            errors.append("source_type_mismatch")
    if event.verification_status == "CROSS-SOURCE VERIFIED":
        if len({s.source_publisher.casefold() for s in event.sources}) < 2:
            errors.append("independent_sources_required")
        for source in event.sources:
            if normalize(event.reported_fact.reported_observation) not in normalize(
                source.evidence_context
            ):
                errors.append("cross_source_support_required")
    if not event.display_summary or event.display_summary != display_summary(
        event.reported_fact, event.derived_context
    ):
        errors.append("unsupported_display_summary")
    if event.llm.llm_used and not event.llm.llm_output_was_validated:
        errors.append("unvalidated_llm_output")
    return sorted(set(errors))
