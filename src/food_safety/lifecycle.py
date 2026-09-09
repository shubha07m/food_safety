"""Bounded continuity: source transport is not a finding about evidence."""

import hashlib
import re
import socket
from datetime import datetime, timedelta

from . import __version__
from .extract import article_text, text_hash
from .models import Event
from .storage import dump, envelope, transition

ACTIVE = {"active", "active_with_warning"}


def source_key(url):
    return "SRC-" + hashlib.sha256(url.encode()).hexdigest()[:20]


def load_checks(root):
    import json

    path = root / "data/source_checks.json"
    return json.loads(path.read_text()).get("checks", {}) if path.exists() else {}


def save_checks(root, checks, at):
    dump(root / "data/source_checks.json", {**envelope([], at), "checks": checks})


def reason_code(error):
    if isinstance(error, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(error, socket.gaierror):
        return "dns_failure"
    value = str(error)
    allowed = {
        "http_403",
        "http_404",
        "http_410",
        "http_429",
        "robots_disallowed",
        "robots_rate_policy_requires_review",
        "unexpected_redirect",
        "challenge_page",
        "extraction_failure",
        "source_identity_changed",
    }
    if value in allowed:
        return value
    if value in {"response_too_large", "compressed_response_rejected"}:
        return "content_too_large" if value == "response_too_large" else "extraction_failure"
    return "network_error" if isinstance(error, OSError) else "extraction_failure"


def checked_document(html):
    """Reject shells rather than treating HTTP 200 as source validation."""
    title, text = article_text(html)
    if re.search(
        r"just a moment|verify you are human|access denied|captcha|enable javascript to continue",
        title + " " + text[:350],
        re.I,
    ):
        raise ValueError("challenge_page")
    if len(text.split()) < 3:
        raise ValueError("extraction_failure")
    return title, text


def availability(checks, url, at, error=None, retry_after=None, review_days=7):
    key = source_key(url)
    previous = checks.get(key, {})
    item = {**previous, "source_id": key, "last_attempt": at.isoformat()}
    if error is None:
        item.update(
            availability="available",
            reason=None,
            failures=0,
            first_failure=None,
            next_retry=None,
            last_success=at.isoformat(),
            review_due=False,
        )
    else:
        failures = previous.get("failures", 0) + 1
        first = previous.get("first_failure") or at.isoformat()
        age = at - datetime.fromisoformat(first)
        hours = 4 if failures == 1 else 12 if failures == 2 else 24 if age.days < 7 else 168
        next_retry = at + timedelta(hours=hours)
        if retry_after and retry_after > next_retry:
            next_retry = retry_after
        reason = reason_code(error)
        removed = reason in {"http_404", "http_410"} and failures >= 3 and age.days >= 1
        item.update(
            availability="removed" if removed else "unavailable",
            reason=reason,
            failures=failures,
            first_failure=first,
            next_retry=next_retry.isoformat(),
            review_due=age.days >= review_days and failures >= 3,
        )
    checks[key] = item
    return item


def due(checks, url, at):
    next_retry = checks.get(source_key(url), {}).get("next_retry")
    return not next_retry or at >= datetime.fromisoformat(next_retry)


def edit(root, event, at, note, **fields):
    data = event.model_dump(mode="json")
    if fields.get("publication_status") not in ACTIVE and fields.get("publication_status"):
        legacy = (
            "SOURCE WITHDRAWN"
            if fields.get("evidence_support_status") == "withdrawn"
            else "PENDING REVIEW"
        )
    else:
        legacy = event.verification_status
    revised = transition(root, event, legacy, note, at, event.review)
    data.update(revised.model_dump(mode="json"))
    if fields.get("publication_status") == "archived_unverifiable":
        data.update(evidence_support_status=event.evidence_support_status, reviewer_hold=False)
    data.update(fields)
    data["pipeline_version"] = __version__
    return Event.model_validate(data)


def technical_failure(root, event, url, checks, at, archive_days=30):
    if event.publication_status not in ACTIVE:
        return event  # Semantic holds are never cleared by a transport event.
    check = checks[source_key(url)]
    data = dict(
        source_availability=check["availability"],
        source_availability_reason=check["reason"],
        last_source_checked_at=at.isoformat(),
        publication_status="active_with_warning",
    )
    required = {s.source_url for s in event.reported_fact.evidence.values()}
    required.update(event.derived_context.derived_context_sources)
    last = event.last_successful_evidence_check_at
    if url in required and last and at - last >= timedelta(days=archive_days):
        data["publication_status"] = "archived_unverifiable"
    return edit(
        root, event, at, "Source access unavailable; historical support is not disproved.", **data
    )


def support_decision(event, source, title, text, other_identities=()):
    """Small deterministic checks. Uncertain semantics require a person, never a guess."""
    if re.search(
        r"(?:this (?:article|report).{0,30}(?:withdrawn|retracted))|(?:এই প্রতিবেদন.{0,30}প্রত্যাহার)",
        text,
        re.I,
    ):
        return "withdrawn"
    notices = re.findall(
        r"(?:correction|corrected|clarification|withdrawn|retracted|সংশোধন|সংশোধনী|প্রত্যাহার)"
        r"[:：]?[^.!?।\n]*",
        text,
        re.I,
    )
    identity = event.reported_fact.establishment_name or event.reported_fact.area
    for notice in notices:
        # Named corrections are local; an unscoped notice conservatively holds every dependent row.
        if identity and identity.casefold() in notice.casefold():
            return "needs_review"
        if not any(name and name.casefold() in notice.casefold() for name in other_identities):
            return "needs_review"
    if source.evidence_context not in text:
        return "needs_review"
    # New immediate negation changes meaning even if the old quote survives verbatim.
    position = text.find(source.evidence_context)
    near = text[max(0, position - 100) : position + len(source.evidence_context) + 100]
    if text_hash(text) != source.text_sha256 and re.search(
        r"\b(?:denied|incorrect|not true|did not|never|false)\b|অস্বীকার|ঘটেনি|সঠিক নয়", near, re.I
    ):
        return "needs_review"
    if title != source.source_title:
        return "needs_review"
    return "supported_as_of"


def recheck(root, event, url, title, text, checks, at, other_identities=()):
    if event.publication_status not in ACTIVE or event.reviewer_hold:
        return event
    source = next(s for s in event.sources if s.source_url == url)
    decision = support_decision(event, source, title, text, other_identities)
    if decision != "supported_as_of":
        return edit(
            root,
            event,
            at,
            "Relevant source support needs reassessment.",
            publication_status="suspended" if decision == "withdrawn" else "needs_review",
            evidence_support_status=decision,
            source_availability="available",
            last_source_checked_at=at.isoformat(),
            reviewer_hold=True,
        )
    data = event.model_dump(mode="json")
    for s in data["sources"]:
        if s["source_url"] == url:
            s.update(text_sha256=text_hash(text), source_revision_id=text_hash(text))
            s["source_language"] = "bn" if any("\u0980" <= c <= "\u09ff" for c in text) else "en"
            s["evidence_language"] = (
                "bn" if any("\u0980" <= c <= "\u09ff" for c in s["evidence_quote"]) else "en"
            )
    all_available = all(
        checks.get(source_key(s.source_url), {}).get("availability", "available") == "available"
        for s in event.sources
    )
    fields = dict(
        sources=data["sources"],
        publication_status="active" if all_available else "active_with_warning",
        source_availability="available" if all_available else "unavailable",
        last_source_checked_at=at.isoformat(),
        source_availability_reason=None if all_available else "other_source_unavailable",
    )
    # Each supporting source must have a successful evidence check, not merely an HTTP check.
    key = source_key(url)
    checks[key].setdefault("supported_records", {})[event.event_id] = at.isoformat()
    times = []
    for field, support in event.reported_fact.evidence.items():
        alternatives = {support.source_url}
        alternatives.update(
            a.source_url for a in event.reviewed_associations if field in a.supported_fields
        )
        supported = [
            checks.get(source_key(u), {}).get("supported_records", {}).get(event.event_id)
            for u in alternatives
        ]
        supported = [t for t in supported if t]
        if supported:
            times.append(max(supported))
    if len(times) == len(event.reported_fact.evidence):
        fields["last_successful_evidence_check_at"] = min(times)
    return edit(
        root,
        event,
        at,
        "Supporting source context revalidated; original evidence retained.",
        **fields,
    )


def expire(root, event, checks, at, archive_days):
    if event.publication_status not in ACTIVE or not event.last_successful_evidence_check_at:
        return event
    if at - event.last_successful_evidence_check_at < timedelta(days=archive_days):
        return event
    return edit(
        root,
        event,
        at,
        "Evidence revalidation overdue; not a finding that reporting was false.",
        publication_status="archived_unverifiable",
        source_availability_reason="revalidation_overdue",
    )
