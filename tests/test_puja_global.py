import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from food_safety.config import settings
from food_safety.puja.freshness import MonitorFetcher, NotModified, due_sources, header, monitor
from food_safety.puja.models import Edition, SourceSpec
from food_safety.puja.pipeline import load_config
from food_safety.puja.regions import load_regions

ROOT = Path(__file__).resolve().parents[1]


def test_five_regions_with_provenance_and_edition_distinction():
    registry = load_regions(ROOT)
    assert {r.region_id for r in registry.regions} == {
        "kolkata",
        "california",
        "london",
        "toronto",
        "melbourne",
    }
    config = load_config(ROOT)
    for region in ("london", "toronto", "melbourne"):
        records = [r for r in config.published if r.region_id == region]
        assert len(records) == 2
        assert all(r.sources and r.coordinate_source and r.address for r in records)
    camden = next(r for r in config.published if r.pandal_id == "london-camden")
    assert camden.edition is None
    assert all(not r.safety_context for r in registry.regions if r.region_id != "kolkata")


def test_edition_dates_timezone_and_evidence_required():
    row = next(r for r in load_config(ROOT).published if r.edition)
    raw = row.edition.model_dump()
    for patch in (
        {"timezone": "Not/AZone"},
        {"end_date": "2026-01-01"},
        {"start_date": "2025-10-01"},
        {"evidence": []},
    ):
        with pytest.raises(ValueError):
            Edition.model_validate(raw | patch)


def test_fair_due_batches_and_simple_seasonality():
    sources = [
        SourceSpec(source_id=f"s{i}", url=f"https://example.org/{i}", publisher="Fixture")
        for i in range(8)
    ]
    at = datetime(2026, 9, 22, tzinfo=UTC)
    receipts = {
        s.source_id: {"last_attempt": (at - timedelta(days=1)).isoformat()} for s in sources[:5]
    }
    assert [s.source_id for s in due_sources(sources, receipts, at, 3)] == ["s5", "s6", "s7"]
    assert not due_sources(sources[:5], receipts, at - timedelta(hours=1), 5)
    winter = datetime(2026, 12, 10, tzinfo=UTC)
    receipts = {
        s.source_id: {"last_attempt": (winter - timedelta(days=6)).isoformat()} for s in sources
    }
    assert not due_sources(sources, receipts, winter, 5)
    assert len(due_sources(sources, receipts, winter + timedelta(days=1), 5)) == 5


def test_conditional_headers_only_target_and_validated_values():
    fetcher = MonitorFetcher([], settings(ROOT))
    url = "https://example.org/puja"
    fetcher.prepare(
        url,
        {
            "content_hash": "a" * 64,
            "etag": '"revision"',
            "last_modified": "Mon, 21 Sep 2026 00:00:00 GMT",
        },
    )
    assert fetcher.conditional_headers(url) == {"If-None-Match": '"revision"'}
    assert fetcher.conditional_headers("https://example.org/robots.txt") == {}
    fetcher.prepare(url, {"content_hash": "a" * 64, "last_modified": "yesterday"})
    assert fetcher.conditional_headers(url) == {"If-Modified-Since": "yesterday"}
    assert header("bad\r\nvalue") is None and header("x" * 513) is None

    class Response:
        status = 304

        def getheader(self, key):
            return None

    with pytest.raises(NotModified):
        fetcher.observe_response(url, Response())
    assert fetcher.metadata["last_modified"] == "yesterday"


def test_unchanged_changed_and_304_are_never_publication_or_model_calls(tmp_path):
    (tmp_path / "config").mkdir()
    source = dict(source_id="fixture", url="https://example.org/puja", publisher="Fixture")
    (tmp_path / "config/puja.yml").write_text(
        yaml.safe_dump({"sources": [source], "published": []})
    )

    class Fetcher:
        metadata = {"etag": '"one"'}
        html = "<article><p>Fixture Puja 2026 at a reviewed venue.</p></article>"
        unchanged = False

        def prepare(self, url, receipt):
            self.receipt = receipt

        def article(self, url):
            if self.unchanged:
                raise NotModified
            return url, self.html

    fetcher = Fetcher()
    at = datetime(2026, 9, 22, tzinfo=UTC)
    assert monitor(tmp_path, at, fetcher)["pending"] == 1
    assert monitor(tmp_path, at + timedelta(hours=2), fetcher)["status"] == "not_due"
    fetcher.unchanged = True
    result = monitor(tmp_path, at + timedelta(days=1), fetcher)
    assert result["unchanged"] == 1 and result["model_calls"] == 0
    state = json.loads((tmp_path / "data/puja_refresh.json").read_text())
    row = state["sources"]["fixture"]
    assert row["pending_change"] and row["last_reviewed_revision"] is None
    assert row["extraction_status"] == "not_requested"
    assert not (tmp_path / "site/data/pandals.json").exists()
    fetcher.unchanged = False
    fetcher.html = "<article><p>Fixture Puja venue changed; review required.</p></article>"
    assert monitor(tmp_path, at + timedelta(days=2), fetcher)["unchanged"] == 0


def test_workflow_puja_step_has_no_llm_environment():
    workflow = yaml.safe_load((ROOT / ".github/workflows/update-data.yml").read_text())
    step = next(
        s
        for s in workflow["jobs"]["candidates"]["steps"]
        if s.get("run") == "python -m food_safety.cli puja refresh"
    )
    assert "env" not in step


def test_monitor_retains_footer_and_structured_event_changes():
    from food_safety.puja.freshness import revision

    source = SourceSpec(source_id="fixture", url="https://example.org", publisher="Fixture")
    html = '<main><p>Puja</p></main><footer>Venue A</footer>'
    assert revision(html, source) != revision(html.replace("Venue A", "Venue B"), source)
    html += '<script type="application/ld+json">{"startDate":"2026-10-17"}</script>'
    assert revision(html, source) != revision(html.replace("2026-10-17", "2026-10-18"), source)


def test_structured_puja_events_use_deterministic_grounded_candidates():
    from food_safety.puja.pipeline import validate_candidate
    from food_safety.puja.structured import events

    event = {
        "@type": "Event",
        "name": "Fixture Durga Puja",
        "startDate": "2026-10-17",
        "location": {
            "name": "Fixture Hall",
            "address": {"addressLocality": "London", "streetAddress": "1 Example Road"},
        },
    }
    content = '<script type="application/ld+json">' + json.dumps(event) + "</script>"
    document, envelope = events(content, "https://example.org/event", "en")
    candidate = validate_candidate(envelope.candidates[0], document)
    assert candidate["required"]["city"]["value"] == "London"
    assert candidate["optional"]["latitude"] is None
    assert candidate["optional"]["venue"]["value"] == "Fixture Hall"
    assert (
        events(content.replace("Fixture Durga Puja", "Another Event"), "https://example.org", "en")
        is None
    )


def test_manual_structured_extract_does_not_invoke_model(tmp_path):
    import shutil

    from food_safety.puja.pipeline import discover, extract

    (tmp_path / "config").mkdir()
    shutil.copy(ROOT / "config/pipeline.yml", tmp_path / "config/pipeline.yml")
    (tmp_path / "config/puja.yml").write_text(
        yaml.safe_dump(
            {
                "sources": [
                    {
                        "source_id": "event",
                        "region_id": "london",
                        "publisher": "Fixture",
                        "url": "https://example.org/event",
                    }
                ],
                "published": [],
            }
        )
    )
    event = {
        "@type": "Event",
        "name": "Fixture Durga Puja",
        "startDate": "2026-10-17",
        "location": {"name": "Fixture Hall", "address": {"addressLocality": "London"}},
    }

    class Fetcher:
        def article(self, url):
            return url, '<script type="application/ld+json">' + json.dumps(event) + "</script>"

    class Model:
        def extract(self, *args):
            raise AssertionError("structured data must not call a model")

    assert discover(tmp_path, fetcher=Fetcher())["fetched"] == 1
    result = extract(tmp_path, extractor=Model())
    assert result["model_calls"] == 0
    assert result["sources"][0]["valid_candidates"] == 1
    assert result["sources"][0]["region_id"] == "london"
