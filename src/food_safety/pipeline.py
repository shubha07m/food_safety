import hashlib
import http.client
import json
import os
import uuid
from collections import Counter
from urllib.parse import urlsplit

import httpx

from . import __version__
from .classify import display_summary
from .config import settings, sources
from .dedupe import associate, same_event, stable_id
from .extract import article_text, text_hash
from .fetch import Fetcher
from .llm import NoLLM, OpenAICompatible
from .models import Event
from .safety import claim_risks, safe_url
from .storage import dump, now, read_events, transaction, transition
from .verify import evidence_errors, publication_errors


def candidate(url, title, text, policy, fields, at, llm=None):
    observation = fields["reported_observation"]
    data = {
        "event_id": stable_id(url, observation),
        "reported_fact": {
            **fields,
            "evidence": {"reported_observation": {"source_url": url, "quote": observation}},
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
            }
        ],
        "record_created_at": at.isoformat(),
        "record_updated_at": at.isoformat(),
        "history": [
            {
                "at": at.isoformat(),
                "status": "PENDING REVIEW",
                "note": "Candidate extracted; source context and event scope need review.",
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
        }
    draft = Event.model_validate(data)
    data["display_summary"] = display_summary(draft.reported_fact, draft.derived_context)
    event = Event.model_validate(data)
    errors = evidence_errors(event, {url: text})
    if errors:
        raise ValueError("evidence_validation_failed")
    return event


def discover(policies, limit, per_source):
    seen = set()
    for policy in policies:
        if not policy.enabled or policy.tier == "discovery":
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


def update(root, max_articles=None, use_llm=False, max_llm_calls=None, fetcher=None):
    from .build import validate

    validate(root)
    cfg, policies = settings(root), sources(root)
    limit = min(max_articles or cfg.max_articles_per_run, cfg.max_articles_per_run)
    if limit < 1 or limit > 10:
        raise ValueError("article_limit_out_of_range")
    calls = cfg.max_llm_calls_per_run if max_llm_calls is None else max_llm_calls
    if calls < 0 or calls > cfg.max_llm_calls_per_run:
        raise ValueError("llm_limit_out_of_range")
    if use_llm and not cfg.llm_enabled:
        raise ValueError("enable_llm_in_config_and_pass_use_llm")
    extractor = OpenAICompatible(calls) if use_llm else NoLLM()
    fetcher = fetcher or Fetcher(policies, cfg)
    events, pending = read_events(root, "events"), read_events(root, "pending")
    rejected = json.loads((root / "data/rejected.json").read_text())["records"]
    at = now()
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
    prior_status = json.loads((root / "data/status.json").read_text())
    # Rotate through previous records as well as configured seeds to detect source changes.
    seeds = list(discover(policies, limit, cfg.max_pages_per_source))
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
    domain_counts = Counter()
    for policy, url in seeds:
        if run["urls_considered"] >= limit:
            break
        if domain_counts[policy.domain] >= cfg.max_pages_per_source:
            continue
        domain_counts[policy.domain] += 1
        scanned.add(policy.domain)
        run["urls_considered"] += 1
        try:
            canonical, html = fetcher.article(url)
            title, text = article_text(html)
            matching = [
                e for e in [*events, *pending] if any(s.source_url == url for s in e.sources)
            ]
            if matching:
                for old in matching:
                    source = next(s for s in old.sources if s.source_url == url)
                    if source.text_sha256 != text_hash(text) or canonical != url:
                        revised = transition(
                            root,
                            old,
                            "SOURCE UPDATED",
                            "Source changed; factual fields suspended for review.",
                            at,
                        )
                        events = [e for e in events if e.event_id != old.event_id]
                        pending = [e for e in pending if e.event_id != old.event_id] + [revised]
                        reasons["source_changed"] += 1
                continue
            if claim_risks(text):
                raise ValueError("suspicious_or_sensitive_content")
            canonical_policy = next(p for p in policies if p.domain == urlsplit(canonical).hostname)
            event = candidate(
                canonical,
                title,
                text,
                canonical_policy,
                extractor.extract(text),
                at,
                extractor if use_llm else None,
            )
            duplicate = next((e for e in [*events, *pending] if same_event(e, event)), None)
            if duplicate:
                merged = associate(duplicate, event, at)
                events = [e for e in events if e.event_id != duplicate.event_id]
                pending = [e for e in pending if e.event_id != duplicate.event_id] + [merged]
                reasons["associated_requires_review"] += 1
            elif (
                cfg.auto_publish
                and os.getenv("AUTO_PUBLISH", "false").lower() == "true"
                and not publication_errors(event, policies, {canonical: text})
            ):
                # Candidates cannot satisfy human review. Reserved for reviewed adapters.
                events.append(event)
                run["records_published"] += 1
            else:
                pending.append(event)
                run["records_pending"] += 1
                reasons["human_review_required"] += 1
        except (
            ValueError,
            OSError,
            KeyError,
            StopIteration,
            http.client.HTTPException,
            httpx.HTTPError,
        ) as exc:
            # Do not persist untrusted article bodies, exception messages or identities.
            reason = (
                "candidate_rejected" if isinstance(exc, ValueError | KeyError) else "fetch_failed"
            )
            reasons[reason] += 1
            run["errors"] += 1
            rejection_id = hashlib.sha256(url.encode()).hexdigest()[:16]
            rejected = [r for r in rejected if r["candidate_id"] != rejection_id]
            rejected.append({"candidate_id": rejection_id, "at": at.isoformat(), "reason": reason})
            run["records_rejected"] += 1
            for old in list(events):
                if any(source.source_url == url for source in old.sources):
                    events.remove(old)
                    pending.append(
                        transition(
                            root,
                            old,
                            "PENDING REVIEW",
                            "Source check failed; record suspended for review.",
                            at,
                        )
                    )
    run.update(
        ended_at=now().isoformat(), sources_scanned=len(scanned), reason_counts=dict(reasons)
    )
    transaction(root, events, pending, rejected, at)
    status = dict(prior_status)
    status.update(
        last_attempt=run["ended_at"],
        last_run_result=(
            "no_sources_enabled" if not scanned else "failed" if run["errors"] else "success"
        ),
        scan_cursor=cursor + run["urls_considered"],
    )
    if scanned:
        status["last_source_scan"] = run["ended_at"]
        if not run["errors"]:
            status["last_successful_update"] = run["ended_at"]
    dump(root / "data/status.json", status)
    dump(root / "data/runs" / f"{run['run_id']}.json", run)
    return run


def review_record(root, record, reviewer, note, fetcher=None):
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
        if event.record_created_at != old.record_created_at or event.history != old.history:
            raise ValueError("preserve_existing_history_and_creation_date")
    fetcher = fetcher or Fetcher(policies, cfg)
    texts = {}
    for source in event.sources:
        canonical, html = fetcher.article(source.source_url)
        if canonical != source.source_url:
            raise ValueError("review_canonical_source_url")
        _, texts[canonical] = article_text(html)
    data = event.model_dump(mode="json")
    status = "SOURCE VERIFIED"
    for source in data["sources"]:
        source["retrieved_at"] = at.isoformat()
    data.update(
        verification_status=status,
        record_updated_at=at.isoformat(),
        review={
            "reviewed_at": at.isoformat(),
            "reviewer": reviewer,
            "note": note,
            "source_context_checked": True,
            "all_fields_supported": True,
        },
    )
    data["history"].append({"at": at.isoformat(), "status": status, "note": note})
    if data["llm"]["llm_used"]:
        data["llm"]["llm_output_was_validated"] = True
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
    rejected = json.loads((root / "data/rejected.json").read_text())["records"]
    transaction(root, events, pending, rejected, at)
    return approved.event_id
