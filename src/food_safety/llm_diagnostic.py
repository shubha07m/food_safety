"""Small private diagnostic for cached source fixtures; not a production gate."""

import json
from collections import Counter
from html import escape
from pathlib import Path
from urllib.parse import urlsplit

from .config import settings, sources
from .extract import article_text
from .llm_publish import publishable_drafts
from .llm_runner import LLMRunner
from .storage import now


def _diagnostic_html(snapshot, source_date=None, anchors=()):
    """Recreate bounded HTML from an ignored frozen-passage snapshot."""
    meta = (
        f'<meta property="article:published_time" content="{escape(source_date)}">'
        if source_date
        else ""
    )
    selected = [
        row
        for row in snapshot["passages"]
        if any(anchor and anchor in row["original_text"] for anchor in anchors)
    ]
    passages = selected or snapshot["passages"]
    body = "".join(f"<p>{escape(row['original_text'])}</p>" for row in passages)
    return f"<head><title>{escape(snapshot['title'])}</title>{meta}</head><article>{body}</article>"


def test_cached_articles(root: Path, max_articles: int, use_llm: bool):
    """Run bounded extraction on an ignored local corpus when one is available."""
    manifest_path = root / ".cache/llm_eval/corpus/manifest.json"
    if not manifest_path.exists():
        raise ValueError("private_llm_test_corpus_missing")
    manifest = json.loads(manifest_path.read_text())
    cfg = settings(root)
    policies = sources(root)
    dates, anchors = {}, {}
    for name in ["events", "pending"]:
        path = root / "data" / f"{name}.json"
        if path.exists():
            for record in json.loads(path.read_text()).get("records", []):
                for source in record.get("sources", []):
                    if source.get("source_date"):
                        dates[source["source_url"]] = source["source_date"]
                    anchors.setdefault(source["source_url"], set()).update(
                        value
                        for value in [source.get("evidence_quote"), source.get("evidence_context")]
                        if value
                    )
    runner = LLMRunner(root, cfg, enabled=use_llm, max_calls=max_articles)
    articles = manifest.get("articles", [])
    if max_articles >= 3:
        first_bn = next((row for row in articles if row.get("source_language") == "bn"), None)
        first_en = next((row for row in articles if row.get("source_language") == "en"), None)
        selected = [row for row in [first_bn, first_en] if row]
        selected.extend(row for row in articles if row not in selected)
    else:
        selected = articles
    reports = []
    for item in selected[:max_articles]:
        fixture = root / ".cache/llm_eval/corpus" / f"{item['key']}.json"
        if not fixture.exists():
            continue
        url = item.get("url") or item.get("source_url")
        language = item.get("language") or item.get("source_language", "und")
        if not url:
            continue
        raw = fixture.read_text()
        snapshot = json.loads(raw)
        html = (
            _diagnostic_html(snapshot, dates.get(url), anchors.get(url, ()))
            if isinstance(snapshot, dict) and snapshot.get("passages")
            else raw
        )
        report = runner.observe(html, url, language)
        publication_pass = 0
        if report.get("status") == "evaluated":
            policy = next((p for p in policies if p.domain == urlsplit(url).hostname), None)
            if policy:
                title, text = article_text(html)
                publication_pass = len(
                    publishable_drafts(cfg, report, html, url, title, text, policy, policies, now())
                )
        reports.append(
            {
                "source_id": report.get("source_id"),
                "language": language,
                "status": report["status"],
                "candidates": len(report.get("candidates", [])),
                "pass": sum(row["decision"] == "pass" for row in report.get("candidates", [])),
                "skip": sum(row["decision"] == "skip" for row in report.get("candidates", [])),
                "publication_pass": publication_pass,
                "publication_skipped": len(report.get("candidates", [])) - publication_pass,
                "publication_skip_reasons": dict(
                    Counter(
                        reason
                        for row in report.get("candidates", [])
                        for reason in row.get("publication_errors", [])
                    )
                ),
                "invalid_candidates": len(report.get("invalid_candidates", [])),
                "latency_seconds": report.get("latency_seconds", 0),
                "usage": report.get("usage", {}),
                "provider_diagnostic": report.get("provider_diagnostic"),
            }
        )
    return {"articles": reports, "counts": dict(runner.counts), "calls": runner.calls}
