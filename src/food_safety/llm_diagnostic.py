"""Small private diagnostic for cached source fixtures; not a production gate."""

import json
from pathlib import Path

from .config import settings
from .llm_runner import LLMRunner


def test_cached_articles(root: Path, max_articles: int, use_llm: bool):
    """Run bounded extraction on an ignored local corpus when one is available."""
    manifest_path = root / ".cache/llm_eval/corpus/manifest.json"
    if not manifest_path.exists():
        raise ValueError("private_llm_test_corpus_missing")
    manifest = json.loads(manifest_path.read_text())
    runner = LLMRunner(root, settings(root), enabled=use_llm, max_calls=max_articles)
    reports = []
    for item in manifest.get("articles", [])[:max_articles]:
        fixture = root / ".cache/llm_eval/corpus" / f"{item['key']}.json"
        if not fixture.exists():
            continue
        url = item.get("url") or item.get("source_url")
        language = item.get("language") or item.get("source_language", "und")
        if not url:
            continue
        report = runner.observe(fixture.read_text(), url, language)
        reports.append({
            "source_id": report.get("source_id"),
            "language": language,
            "status": report["status"],
            "candidates": len(report.get("candidates", [])),
            "pass": sum(row["decision"] == "pass" for row in report.get("candidates", [])),
            "review": sum(row["decision"] == "review" for row in report.get("candidates", [])),
            "reject": sum(row["decision"] == "reject" for row in report.get("candidates", [])),
            "invalid_candidates": len(report.get("invalid_candidates", [])),
            "latency_seconds": report.get("latency_seconds", 0),
            "usage": report.get("usage", {}),
            "provider_diagnostic": report.get("provider_diagnostic"),
        })
    return {"articles": reports, "counts": dict(runner.counts), "calls": runner.calls}
