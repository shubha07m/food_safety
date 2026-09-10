import hashlib
import http.client
import json
import os
import uuid
from collections import Counter
from urllib.parse import urlsplit

import httpx

from . import __version__, lifecycle
from .classify import display_summary
from .community import load_leads
from .config import settings, sources
from .dedupe import area_key, same_event, stable_id
from .discovery import BraveSearch, feed_candidates, page_candidates, sitemap_candidates
from .extract import text_hash
from .fetch import Fetcher, FetchError
from .llm_publish import publishable_drafts
from .llm_runner import LLMRunner
from .models import Event
from .safety import safe_url
from .storage import dump, now, read_events, read_rejected, transaction, transition
from .verify import evidence_errors, publication_errors


def candidate(url, title, text, policy, fields, at, llm=None, validate_evidence=True):
    observation = fields["reported_observation"]
    evidence_language = (
        "bn" if any("\u0980" <= character <= "\u09ff" for character in observation) else "en"
    )
    data = {
        "event_id": stable_id(url, observation + "|" + (fields.get("establishment_name") or "")),
        "reported_fact": {
            **fields,
            "evidence": {
                key: {"source_url": url, "quote": observation}
                for key, value in fields.items()
                if value is not None and key != "legal_finding_status"
            },
        },
        "sources": [
            {
                "source_url": url,
                "source_title": title,
                "source_publisher": policy.name,
                "source_type": {"A": "official", "B": "news", "C": "other"}[policy.tier],
                "tier": policy.tier,
                "retrieved_at": at.isoformat(),
                "text_sha256": text_hash(text),
                "evidence_quote": observation,
                "evidence_context": observation,
                "source_language": (
                    policy.language if policy.language in {"en", "bn"} else evidence_language
                ),
                "evidence_language": evidence_language,
            }
        ],
        "record_created_at": at.isoformat(),
        "record_updated_at": at.isoformat(),
        "history": [
            {
                "at": at.isoformat(),
                "status": "PENDING REVIEW",
                "note": "Candidate extracted; publication validation is not yet complete.",
            }
        ],
    }
    if llm:
        data["llm"] = {
            "llm_used": True,
            "llm_provider": llm.provider,
            "llm_model": llm.model,
            "llm_task": "candidate verbatim observation",
            "llm_pipeline_version": __version__,
            "llm_output_was_validated": False,
            "llm_task_version": "candidate_span_v1",
            "llm_used_at": at.isoformat(),
            "source_revision_id": text_hash(text),
            "fields_proposed": sorted(fields),
            "validation_result": "pending",
        }
    draft = Event.model_validate(data)
    data["display_summary"] = display_summary(draft.reported_fact, draft.derived_context)
    event = Event.model_validate(data)
    errors = evidence_errors(event, {url: text}) if validate_evidence else []
    if errors:
        raise ValueError("evidence_validation_failed")
    return event


def discover(policies, limit, per_source):
    seen = set()
    for policy in policies:
        if (
            not policy.enabled
            or policy.tier == "discovery"
            or policy.discovery_method == "manual_only"
        ):
            continue
        for raw in policy.urls[:per_source]:
            url = safe_url(raw)
            if urlsplit(url).hostname != policy.domain:
                raise ValueError("seed_outside_source_domain")
            if url in seen:
                continue
            if len(seen) >= limit:
                return
            seen.add(url)
            yield policy, url


def update(
    root, max_articles=None, use_llm=None, max_llm_calls=None, fetcher=None, llm_extractor=None
):
    from .build import validate

    validate(root)
    cfg, policies = settings(root), sources(root)
    limit = min(max_articles or cfg.max_articles_per_run, cfg.max_articles_per_run)
    if limit < 1 or limit > 30:
        raise ValueError("article_limit_out_of_range")
    calls = cfg.max_llm_calls_per_run if max_llm_calls is None else max_llm_calls
    if calls < 0 or calls > cfg.max_llm_calls_per_run:
        raise ValueError("llm_limit_out_of_range")
    llm_runner = LLMRunner(root, cfg, use_llm, calls, llm_extractor)
    discovery_fetcher = fetcher or Fetcher(
        policies, cfg.model_copy(update={"max_response_bytes": cfg.max_discovery_response_bytes})
    )
    fetcher = fetcher or Fetcher(policies, cfg)
    events, pending = read_events(root, "events"), read_events(root, "pending")
    initial_published_ids = {event.event_id for event in events}
    rejected = read_rejected(root)["records"]
    at = now()
    checks = lifecycle.load_checks(root)
    run = {
        "run_id": uuid.uuid4().hex,
        "started_at": at.isoformat(),
        "sources_scanned": 0,
        "urls_considered": 0,
        "records_published": 0,
        "records_pending": 0,
        "records_rejected": 0,
        "errors": 0,
        "reason_counts": {},
    }
    reasons, scanned = Counter(), set()
    coverage = {
        p.name: {
            "publisher": p.name,
            "domain": p.domain,
            "language": p.language,
            "discovery_status": p.discovery_status,
            "automation": "manual_only" if p.discovery_method == "manual_only" else "bounded",
            "manual_only_reason": p.manual_only_reason,
            "mechanisms": [],
            "last_successful_discovery": None,
            "article_fetch_status": "not_attempted",
            "automatic_extraction_status": "not_attempted",
            "candidate_urls_seen": 0,
            "fetched": 0,
            "records_produced": 0,
            "failures": Counter(),
        }
        for p in policies
    }
    prior_status = json.loads((root / "data/status.json").read_text())
    # Rotate through previous records as well as configured seeds to detect source changes.
    seeds = list(discover(policies, cfg.max_discovery_candidates_per_run, cfg.max_pages_per_source))
    existing_urls = {url for _, url in seeds}
    for event in events:
        for source in event.sources:
            policy = next(
                (p for p in policies if p.domain == urlsplit(source.source_url).hostname), None
            )
            if policy and policy.enabled and source.source_url not in existing_urls:
                seeds.append((policy, source.source_url))
                existing_urls.add(source.source_url)
    cursor = int(prior_status.get("scan_cursor", 0))
    if seeds:
        offset = cursor % len(seeds)
        seeds = seeds[offset:] + seeds[:offset]
    # Discovery is broad but bounded. Index/feed/sitemap content is never evidence.
    endpoints = [
        (p, u, parser)
        for p in policies
        if p.enabled and p.tier in {"A", "B"} and p.discovery_method != "manual_only"
        for urls, parser in [
            (p.feed_urls, feed_candidates),
            (p.sitemap_urls, sitemap_candidates),
            (p.discovery_pages, page_candidates),
        ]
        for u in urls
    ]
    discovered = []
    if endpoints:
        start = cursor % len(endpoints)
        rotating = endpoints[start:] + endpoints[:start]
        for policy, endpoint, parser in rotating[: cfg.max_discovery_endpoints_per_run]:
            mechanism = parser.__name__.replace("_candidates", "")
            coverage[policy.name]["mechanisms"].append(mechanism)
            try:
                _, body = discovery_fetcher.article(endpoint)
                urls = parser(body, policy, cfg.max_discovery_candidates_per_run)
                coverage[policy.name]["last_successful_discovery"] = at.isoformat()
                discovered.extend((policy, u) for u in urls)
            except (ValueError, OSError, httpx.HTTPError) as exc:
                code = lifecycle.reason_code(exc)
                coverage[policy.name]["failures"][code] += 1
                reasons["discovery_endpoint_unavailable"] += 1
                run["errors"] += 1
    if cfg.search_provider == "brave":
        try:
            searched = BraveSearch(policies, cfg.max_search_queries_per_run).discover(
                cfg.max_discovery_candidates_per_run
            )
            for policy, _ in searched:
                coverage[policy.name]["mechanisms"].append("search_api")
                coverage[policy.name]["last_successful_discovery"] = at.isoformat()
            discovered.extend(searched)
        except (ValueError, httpx.HTTPError):
            reasons["search_provider_unavailable"] += 1
            run["errors"] += 1
    community = load_leads(root, policies)
    for policy, _ in community:
        coverage[policy.name]["mechanisms"].append("approved_community_lead")
    discovered.extend(community)
    # Reserve half the run for rechecking older sources; avoid feed starvation.
    known = {s.source_url for e in events for s in e.sources}
    maintenance = [item for item in seeds if item[1] in known]
    new = [item for item in [*discovered, *seeds] if item[1] not in known]
    unique_new = {(policy.name, url) for policy, url in new}
    for publisher, _ in unique_new:
        coverage[publisher]["candidate_urls_seen"] += 1
    new_budget = min(cfg.max_new_articles_per_run, limit)
    maintenance_budget = min(cfg.max_rechecks_per_run, max(0, limit - new_budget))
    combined = new[:new_budget] + maintenance[:maintenance_budget]
    seen_urls = set()
    seeds = []
    for item in combined:
        if item[1] not in seen_urls:
            seeds.append(item)
            seen_urls.add(item[1])
    domain_counts = Counter()
    retired_path = root / "data/retired.json"
    retired = json.loads(retired_path.read_text())["records"] if retired_path.exists() else []
    suspended = {h for row in retired for h in row.get("source_url_sha256", [])}
    host_failures = Counter()
    for policy, url in seeds:
        if run["urls_considered"] >= limit:
            break
        if domain_counts[policy.domain] >= cfg.max_pages_per_source:
            continue
        if host_failures[policy.domain] >= 2:
            reasons["host_circuit_open"] += 1
            continue
        if not lifecycle.due(checks, url, at):
            reasons["retry_not_due"] += 1
            continue
        if hashlib.sha256(url.encode()).hexdigest() in suspended:
            reasons["suspended_source_requires_review"] += 1
            run["urls_considered"] += 1
            continue
        domain_counts[policy.domain] += 1
        scanned.add(policy.domain)
        run["urls_considered"] += 1
        try:
            canonical, html = fetcher.article(url)
            if canonical != url:
                raise ValueError("unexpected_redirect")
            title, text = lifecycle.checked_document(html)
            lifecycle.availability(checks, url, at)
            coverage[policy.name]["fetched"] += 1
            coverage[policy.name]["article_fetch_status"] = "accessible"
            matching = [
                e for e in [*events, *pending] if any(s.source_url == url for s in e.sources)
            ]
            published_matching = [old for old in matching if old.first_published_at]
            if published_matching:
                for old in published_matching:
                    others = [
                        e.reported_fact.establishment_name or e.reported_fact.area
                        for e in matching
                        if e.event_id != old.event_id
                    ]
                    revised = lifecycle.recheck(
                        root,
                        old,
                        url,
                        title,
                        text,
                        checks,
                        at,
                        others,
                        policy.language if policy.language in {"en", "bn"} else None,
                    )
                    events = [e for e in events if e.event_id != old.event_id]
                    pending = [e for e in pending if e.event_id != old.event_id]
                    (events if revised.publication_status in lifecycle.ACTIVE else pending).append(
                        revised
                    )
                    reasons[revised.publication_status] += 1
                continue
            canonical_policy = next(p for p in policies if p.domain == urlsplit(canonical).hostname)
            auto_enabled = cfg.auto_publish and os.getenv("AUTO_PUBLISH", "true").lower() == "true"
            model_report = llm_runner.observe(html, url, policy.language)
            drafts = []
            try:
                assisted = publishable_drafts(
                    cfg,
                    model_report,
                    html,
                    canonical,
                    title,
                    text,
                    canonical_policy,
                    policies,
                    at,
                )
                ids = {e.event_id for e in events + pending}
                drafts.extend(draft for draft in assisted if draft.event_id not in ids)
                for row in model_report.get("candidates", []):
                    for error in row.get("publication_errors", []):
                        reasons[f"llm_skip:{error}"] += 1
            except Exception:
                reasons["llm_policy_processing_failed"] += 1
            coverage[policy.name]["records_produced"] += len(drafts)
            coverage[policy.name]["automatic_extraction_status"] = model_report.get("status")
            if len(drafts) > 1:
                ids = [draft.event_id for draft in drafts]
                for draft in drafts:
                    draft.related_record_ids = [value for value in ids if value != draft.event_id]
            for event in drafts:
                ambiguous_overlap = event.automatic_validation and any(
                    not event.reported_fact.establishment_name
                    and not old.reported_fact.establishment_name
                    and area_key(old.reported_fact.area) == area_key(event.reported_fact.area)
                    and old.sources[0].source_date
                    and event.sources[0].source_date
                    and abs((old.sources[0].source_date - event.sources[0].source_date).days) <= 7
                    and old.record_scope == event.record_scope
                    for old in [*events, *pending]
                )
                duplicate = next((e for e in [*events, *pending] if same_event(e, event)), None)
                if duplicate:
                    reasons["duplicate_skipped"] += 1
                elif ambiguous_overlap:
                    reasons["ambiguous_duplicate_skipped"] += 1
                elif auto_enabled and not publication_errors(event, policies, {canonical: text}):
                    events.append(event)
                    event.first_published_at = event.first_published_at or at
                    run["records_published"] += 1
                else:
                    run["records_rejected"] += 1
                    reasons["llm_candidate_skipped"] += 1
        except (
            ValueError,
            OSError,
            KeyError,
            StopIteration,
            http.client.HTTPException,
            httpx.HTTPError,
        ) as exc:
            # Do not persist untrusted article bodies, exception messages or identities.
            retrieval_failed = isinstance(
                exc, (FetchError, OSError, httpx.HTTPError, http.client.HTTPException)
            )
            reason = "fetch_failed" if retrieval_failed else "candidate_rejected"
            coverage[policy.name]["failures"][reason] += 1
            matching_public = [e for e in events if any(s.source_url == url for s in e.sources)]
            if retrieval_failed or matching_public:
                lifecycle.availability(
                    checks, url, at, exc, getattr(exc, "retry_after", None), cfg.review_after_days
                )
                host_failures[policy.domain] += 1
            reasons[reason] += 1
            affected_public = any(s.source_url == url for e in events for s in e.sources)
            if retrieval_failed or affected_public:
                run["errors"] += 1
            rejection_id = hashlib.sha256(url.encode()).hexdigest()[:16]
            rejected = [r for r in rejected if r["candidate_id"] != rejection_id]
            rejected.append({"candidate_id": rejection_id, "at": at.isoformat(), "reason": reason})
            run["records_rejected"] += 1
            for old in list(events):
                if any(source.source_url == url for source in old.sources):
                    events.remove(old)
                    revised = lifecycle.technical_failure(
                        root, old, url, checks, at, cfg.archive_after_days
                    )
                    (events if revised.publication_status in lifecycle.ACTIVE else pending).append(
                        revised
                    )
    for event in list(events):
        revised = lifecycle.expire(root, event, checks, at, cfg.archive_after_days)
        if revised.publication_status not in lifecycle.ACTIVE:
            events.remove(event)
            pending.append(revised)
    lifecycle.save_checks(root, checks, at)
    run.update(
        llm_calls=llm_runner.calls,
        llm_status_counts=dict(llm_runner.counts),
        ended_at=now().isoformat(),
        sources_scanned=len(scanned),
        reason_counts=dict(reasons),
        host_failures=dict(host_failures),
        review_due_sources=sum(bool(c.get("review_due")) for c in checks.values()),
    )
    transaction(root, events, pending, rejected, at)
    status = dict(prior_status)
    status["held_from_last_scan"] = run["records_pending"] + len(
        initial_published_ids - {event.event_id for event in events}
    )
    if os.getenv("GITHUB_ACTIONS") == "true":
        status["scheduled_refresh_hours"] = 2
    status.update(
        last_attempt=run["ended_at"],
        last_run_result=(
            "failed" if run["errors"] else "no_sources_checked" if not scanned else "success"
        ),
        scan_cursor=cursor + run["urls_considered"],
    )
    if scanned:
        status["last_source_scan"] = run["ended_at"]
        if not run["errors"]:
            status["last_successful_update"] = run["ended_at"]
    dump(root / "data/status.json", status)
    dump(root / "data/runs" / f"{run['run_id']}.json", run)
    _write_coverage(root, coverage, at)
    return run


def _write_coverage(root, coverage, at):
    rows = []
    for value in coverage.values():
        row = dict(value)
        row["mechanisms"] = sorted(set(row["mechanisms"]))
        row["failures"] = dict(row["failures"])
        rows.append(row)
    payload = {"generated_at": at.isoformat(), "publishers": rows}
    dump(root / "reports/source_coverage.json", payload)
    lines = [
        "# Source coverage",
        "",
        f"Generated: `{at.isoformat()}`. Discovery leads are not evidence or publication.",
        "",
        "| Publisher | Language | Status | Mechanisms | Seen | Fetched | Records | Failures |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['publisher']} | {row['language']} | {row['discovery_status']} | "
            f"{', '.join(row['mechanisms']) or 'none'} | {row['candidate_urls_seen']} | "
            f"{row['fetched']} | {row['records_produced']} | "
            f"{', '.join(f'{k}:{v}' for k, v in row['failures'].items()) or 'none'} |"
        )
    (root / "reports/source_coverage.md").write_text("\n".join(lines) + "\n")


def review_record(root, record, reviewer, note, fetcher=None, cross_source=False):
    """Explicit maintainer attestation, with a fresh fetch of all supporting sources."""
    from .build import validate

    validate(root)
    cfg, policies, at = settings(root), sources(root), now()
    event = Event.model_validate(record)
    pending, events = read_events(root, "pending"), read_events(root, "events")
    old = next((e for e in [*pending, *events] if e.event_id == event.event_id), None)
    if any(e.event_id != event.event_id and same_event(e, event) for e in [*pending, *events]):
        raise ValueError("existing_event_requires_source_association_and_existing_id")
    if old:
        if event.first_published_at != old.first_published_at:
            raise ValueError("preserve_first_publication_date")
        if event.record_created_at != old.record_created_at or event.history != old.history:
            raise ValueError("preserve_existing_history_and_creation_date")
    fetcher = fetcher or Fetcher(policies, cfg)
    texts = {}
    for source in event.sources:
        canonical, html = fetcher.article(source.source_url)
        if canonical != source.source_url:
            raise ValueError("review_canonical_source_url")
        title, texts[canonical] = lifecycle.checked_document(html)
        if title != source.source_title:
            raise ValueError("review_source_identity_changed")
    data = event.model_dump(mode="json")
    status = "CROSS-SOURCE VERIFIED" if cross_source else "SOURCE VERIFIED"
    for source in data["sources"]:
        source["retrieved_at"] = at.isoformat()
    data.update(
        verification_status=status,
        record_updated_at=at.isoformat(),
        automatic_validation=None,
        review={
            "reviewed_at": at.isoformat(),
            "reviewer": reviewer,
            "note": note,
            "source_context_checked": True,
            "all_fields_supported": True,
        },
        publication_status="active",
        evidence_support_status="supported_as_of",
        first_published_at=data.get("first_published_at") or at.isoformat(),
        last_successful_evidence_check_at=at.isoformat(),
        last_source_checked_at=at.isoformat(),
        source_availability="available",
        source_availability_reason=None,
        reviewer_hold=False,
    )
    data["history"].append({"at": at.isoformat(), "status": status, "note": note})
    if data["llm"]["llm_used"]:
        data["llm"]["llm_output_was_validated"] = True
        data["llm"]["validation_result"] = "passed"
    approved = Event.model_validate(data)
    errors = publication_errors(approved, policies, texts)
    if errors:
        raise ValueError(", ".join(errors))
    if old:
        revision = transition(root, old, status, note, at, data["review"])
        data["history"] = [item.model_dump(mode="json") for item in revision.history]
        approved = Event.model_validate(data)
    pending = [e for e in pending if e.event_id != approved.event_id]
    events = [e for e in events if e.event_id != approved.event_id] + [approved]
    rejected = read_rejected(root)["records"]
    transaction(root, events, pending, rejected, at)
    return approved.event_id
