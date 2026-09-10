"""Explicit, private, bounded corpus preparation and repeatable shadow evaluation."""

import hashlib
import json
from collections import Counter
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field

from .automatic import automatic_matches
from .config import settings, sources
from .documents import PARSER_VERSION, DocumentRevision, freeze_document
from .fetch import Fetcher, FetchError
from .lifecycle import checked_document
from .llm_shadow import ShadowRunner
from .storage import dump, now, read_events


class GoldRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_scope: str
    fields: dict[str, str]
    evidence: dict[str, list[dict[str, str]]] = Field(default_factory=dict)


class GoldArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_revision_id: str
    reviewed: bool = False
    exhaustive: bool = False
    story_group: str | None = None
    split: str | None = None
    relevant: bool | None = None
    records: list[GoldRecord] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    ambiguity_markers: list[str] = Field(default_factory=list)
    reviewer_minutes: float | None = None


def prepare_corpus(root, max_articles=30, fetcher=None):
    """Known source URLs only; no crawling, publication or model calls. Reuse revisions."""
    if not 1 <= max_articles <= 30:
        raise ValueError("corpus_limit_1_to_30")
    cfg = settings(root)
    policies = [
        p
        for p in sources(root)
        if p.enabled
        and p.tier in {"A", "B"}
        and p.discovery_status != "blocked"
        and p.discovery_method != "manual_only"
    ]
    fetcher = fetcher or Fetcher(policies, cfg)
    queues = {p.domain: list(p.urls) for p in policies}
    for event in read_events(root, "events"):
        for source in event.sources:
            host = urlsplit(source.source_url).hostname
            if host in queues and source.source_url not in queues[host]:
                queues[host].append(source.source_url)
    ordered = sorted(policies, key=lambda p: p.language != "bn")
    private = root / ".cache/llm_eval/corpus"
    manifest_path = private / "manifest.json"
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {"articles": []}
    articles = {a["source_url"]: a for a in old["articles"]}
    seen, failed_hosts, attempts, reused = set(), set(), 0, 0
    diagnostics = []
    # Round robin; at most five articles per host and one failed request before circuit break.
    for index in range(min(5, cfg.max_pages_per_source)):
        for policy in ordered:
            if len(seen) >= max_articles:
                break
            queue = queues[policy.domain]
            if index >= len(queue) or policy.domain in failed_hosts:
                continue
            url = queue[index]
            if url in seen:
                continue
            seen.add(url)
            if url in articles:
                saved = private / f"{articles[url]['key']}.json"
                if json.loads(saved.read_text())["parser_version"] == PARSER_VERSION:
                    reused += 1
                    continue
            attempts += 1
            try:
                canonical, body = fetcher.article(url)
                checked_document(body)
                if urlsplit(canonical).hostname != policy.domain:
                    raise ValueError("source_identity_changed")
                document = freeze_document(body, canonical, policy.language)
                key = hashlib.sha256((url + document.source_revision_id).encode()).hexdigest()[:20]
                dump(private / f"{key}.json", document.model_dump(mode="json"))
                # A template is not a gold label; never infer maintainer approval.
                dump(
                    private / f"{key}.gold.json",
                    GoldArticle(
                        source_revision_id=document.source_revision_id,
                    ).model_dump(),
                )
                articles[url] = {
                    "key": key,
                    "source_url": url,
                    "publisher": policy.name,
                    "source_language": policy.language,
                    "retrieved_at": now().isoformat(),
                    "source_revision_id": document.source_revision_id,
                    "passages": len(document.passages),
                    "characters": sum(len(p.original_text) for p in document.passages),
                }
            except (FetchError, ValueError, OSError) as exc:
                failed_hosts.add(policy.domain)
                diagnostics.append(
                    {
                        "publisher": policy.name,
                        "source_url": url,
                        "reason": str(exc) if isinstance(exc, FetchError) else type(exc).__name__,
                    }
                )
    manifest = {
        "at": now().isoformat(),
        "private": True,
        "articles": list(articles.values()),
        "last_acquisition": {"attempts": attempts, "reused": reused, "failures": diagnostics},
    }
    dump(manifest_path, manifest)
    return {
        "corpus_articles": len(articles),
        "attempts": attempts,
        "reused": reused,
        "failures": len(diagnostics),
        "languages": dict(Counter(a["source_language"] for a in articles.values())),
        "gold_reviewed": sum(
            GoldArticle.model_validate_json(
                (private / f"{a['key']}.gold.json").read_text()
            ).reviewed
            for a in articles.values()
        ),
    }


def compare_records(predicted, expected):
    """Exact raw field matching, not semantic similarity. Gold aliases require explicit labels."""
    used, matched_records, matched_fields, predicted_fields = set(), 0, 0, 0
    for candidate in predicted:
        fields = candidate["fields"]
        predicted_fields += len(fields)
        matches = []
        for i, gold in enumerate(expected):
            if i in used or candidate["record_scope"] != gold["record_scope"]:
                continue
            # Do not attach one business's quantity/action to a different business.
            identity = ["area", "establishment_name"]
            if any(fields.get(k) != gold["fields"].get(k) for k in identity):
                continue
            overlap = sum(gold["fields"].get(k) == v for k, v in fields.items())
            matches.append((overlap, i))
        if matches:
            overlap, index = max(matches)
            used.add(index)
            matched_fields += overlap
            if all(fields.get(k) == v for k, v in expected[index]["fields"].items()):
                matched_records += 1
    expected_fields = sum(len(row["fields"]) for row in expected)
    return {
        "record_precision": matched_records / len(predicted) if predicted else None,
        "record_recall": matched_records / len(expected) if expected else None,
        "field_precision": matched_fields / predicted_fields if predicted_fields else None,
        "field_recall": matched_fields / expected_fields if expected_fields else None,
        "predicted_records": len(predicted),
        "expected_records": len(expected),
        "matched_records": matched_records,
        "matched_fields": matched_fields,
        "predicted_fields": predicted_fields,
        "expected_fields": expected_fields,
    }


def evaluate_corpus(root, max_articles=30, use_llm=False, extractor=None):
    """No fetch. Live inference requires the explicit CLI flag and provider credentials."""
    if not 1 <= max_articles <= 60:
        raise ValueError("evaluation_limit_1_to_60")
    private = root / ".cache/llm_eval/corpus"
    manifest = json.loads((private / "manifest.json").read_text())
    cfg = settings(root)
    runner = ShadowRunner(root, cfg, max_calls=None if use_llm else 0, extractor=extractor)
    reports, split_groups = [], {}
    for article in manifest["articles"][:max_articles]:
        key = article["key"]
        document = DocumentRevision.model_validate_json((private / f"{key}.json").read_text())
        gold = GoldArticle.model_validate_json((private / f"{key}.gold.json").read_text())
        if gold.source_revision_id != document.source_revision_id:
            raise ValueError("gold_revision_mismatch")
        if gold.reviewed and (not gold.exhaustive or not gold.story_group or not gold.split):
            raise ValueError("gold_requires_exhaustive_story_group_and_split")
        if gold.reviewed:
            previous = split_groups.setdefault(gold.story_group, gold.split)
            if previous != gold.split:
                raise ValueError("story_leakage_between_splits")
        text = "\n".join(p.original_text for p in document.passages)
        deterministic = automatic_matches(text)
        shadow = runner.observe_document(document, deterministic)
        expected = [row.model_dump() for row in gold.records]
        predicted = [
            {"record_scope": scope, "fields": fields} for _, fields, scope in deterministic
        ]
        model_rows = [
            {
                "record_scope": row["record_scope"],
                "fields": {
                    ("reported_action" if k == "actions.0" else k): v["raw_value"]
                    for k, v in row["supported_fields"].items()
                },
            }
            for row in shadow.get("candidates", [])
        ]
        reports.append(
            {
                "key": key,
                "language": article["source_language"],
                "publisher": article["publisher"],
                "gold_reviewed": gold.reviewed,
                "deterministic_candidates": len(predicted),
                "model_status": shadow["status"],
                "model_candidates": len(model_rows),
                "deterministic_metrics": compare_records(predicted, expected)
                if gold.reviewed
                else None,
                "validated_shadow_metrics": compare_records(model_rows, expected)
                if gold.reviewed and shadow["status"] == "evaluated"
                else None,
                "reviewer_minutes": gold.reviewer_minutes,
                "latency_seconds": shadow.get("latency_seconds"),
                "usage": shadow.get("usage"),
            }
        )
    summary = {
        "at": now().isoformat(),
        "private": True,
        "articles": reports,
        "gold_reviewed": sum(r["gold_reviewed"] for r in reports),
        "model_calls": runner.calls,
        "model_status_counts": dict(runner.counts),
        "deterministic_candidates": sum(r["deterministic_candidates"] for r in reports),
        "promotion_eligible": False,
        "unmeasured_metrics": [
            "raw_model_field_precision",
            "entity_quantity_association_accuracy",
            "cost_per_additional_accepted_record",
            "reviewer_minutes_per_accepted_record",
        ],
        "limitations": "Small evaluation scaffold, not an auto-publication qualification. "
        "Metrics are per article and exclude unreviewed gold; no absent-model zero scores.",
    }
    dump(root / ".cache/llm_eval/evaluation.json", summary)
    return {k: v for k, v in summary.items() if k != "articles"} | {"articles": len(reports)}
