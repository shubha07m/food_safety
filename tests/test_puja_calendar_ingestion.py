"""Ingestion repairs must not promote dates, geography, or publication state."""

import json
from pathlib import Path

import pytest
from test_fetch import Response
from test_fetch import fetch_mock as _fetch_mock
from test_puja_profiles import Model, campaign

from food_safety.config import Settings
from food_safety.fetch import Fetcher, FetchError
from food_safety.puja import leads
from food_safety.puja.pipeline import PujaFetcher
from food_safety.puja.structured import events

EVENT_URL = "https://www.sanskriti.org/event-details/sanskriti-durga-puja-2026"
fetch_mock = _fetch_mock


@pytest.mark.parametrize("body_size,ok", [(1076080, True), (1280 * 1024 + 1, False)])
@pytest.mark.parametrize("declared", [True, False])
def test_sanskriti_bounded_puja_only_allowance(fetch_mock, body_size, ok, declared):
    base, responses, _ = fetch_mock
    puja = PujaFetcher([], Settings(max_response_bytes=1048576))
    puja.domains = {"www.sanskriti.org"}
    headers = {"Content-Length": str(body_size)} if declared else {}
    responses.append(Response(b"x" * body_size, headers=headers))
    if ok:
        assert len(puja.raw(EVENT_URL)[1]) == body_size
    else:
        with pytest.raises(FetchError, match="response_too_large"):
            puja.raw(EVENT_URL)
    assert puja.settings.max_response_bytes == 1048576
    assert puja.response_limit("https://www.sanskriti.org/") == 1048576
    assert puja.response_limit("https://www.sanskriti.org/robots.txt") == 1048576
    base.domains = puja.domains
    base.settings = puja.settings
    responses.append(Response(b"x" * 1076080))
    with pytest.raises(FetchError, match="response_too_large"):
        base.raw(EVENT_URL)  # Food Safety's fetcher remains unchanged.
    assert type(base) is Fetcher


@pytest.mark.parametrize("host", ["bascweb.org", "durga.valleybengali.org"])
def test_robots_403_never_bypassed(fetch_mock, host):
    _, responses, connections = fetch_mock
    puja = PujaFetcher([], Settings())
    puja.domains = {host}
    puja.missing_robots_hosts = {host}
    responses.append(Response(status=403))
    with pytest.raises(FetchError, match="http_403"):
        puja.article("https://" + host + "/")
    assert len(connections) == 1


@pytest.mark.parametrize(
    "target,reason",
    [
        ("http://127.0.0.1/private", "private_url"),
        ("http://www.sanskriti.org/", "insecure_redirect"),
        ("https://unknown.example/", "domain_not_enabled"),
    ],
)
def test_allowance_preserves_redirect_safety(fetch_mock, target, reason):
    _, responses, _ = fetch_mock
    puja = PujaFetcher([], Settings())
    puja.domains = {"www.sanskriti.org"}
    responses.append(Response(status=302, headers={"Location": target}))
    with pytest.raises(ValueError, match=reason):
        puja.raw(EVENT_URL)


def event_html(start, end, location=None):
    event = {
        "@type": "Event",
        "name": "Fixture Durga Puja 2026",
        "startDate": start,
        "endDate": end,
        "location": location,
    }
    return '<script type="application/ld+json">' + json.dumps(event) + "</script>"


@pytest.mark.parametrize(
    "start,end,expected",
    [
        ("2026-10-09T17:30:00-07:00", "2026-10-11T22:00:00-07:00", ("2026-10-09", "2026-10-11")),
        ("2026-10-16T18:00:00-07:00", "2026-10-18T18:00:00-07:00", ("2026-10-16", "2026-10-18")),
        ("2026-10-09T00:30:00+14:00", "2026-10-11T23:30:00-12:00", ("2026-10-09", "2026-10-11")),
        ("2026-10-09", "2026-10-11", ("2026-10-09", "2026-10-11")),
    ],
)
@pytest.mark.parametrize("location", [None, {"name": "Fixture Hall", "address": "Literal address"}])
def test_structured_profile_range_without_geography(
    tmp_path, monkeypatch, start, end, expected, location
):
    html = event_html(start, end, location)
    file = campaign(tmp_path, monkeypatch, html)
    seeds = json.loads(file.read_text())
    seeds[0].update(mode="profile", accepted_identity="Fixture Durga Puja 2026")
    file.write_text(json.dumps(seeds))
    model = Model()
    model.calls = 0
    model.fail = True
    result = leads.run(tmp_path, file, "date-repair", 1, extractor=model)
    assert result["candidates"] == 1 and model.calls == 0
    packet = json.loads((tmp_path / ".cache/puja/campaigns/date-repair/review.json").read_text())
    item = packet["sources"][0]["candidates"][0]
    d = item["supported_dates"]
    assert (d["start_date"], d["end_date"]) == expected
    assert d["evidence"]["original_quote"] == start
    assert d["end_evidence"]["original_quote"] == end
    assert d["source_revision_id"] and d["source_url"]
    assert item["fields"]["start_date"]["value"] == start  # Never invent a source literal.
    assert item["fields"]["end_date"]["value"] == end
    assert item["fields"]["venue"] is None and item["fields"]["address"] is None
    assert item["map_eligibility"] == "not_reviewed"
    assert item["publication"] == "requires_human_approval"
    assert not (tmp_path / "data/pandals.json").exists()
    leads.run(tmp_path, file, "date-repair", 1, extractor=model)
    assert model.calls == 0


@pytest.mark.parametrize("end", ["2026-10-08", "2027-10-11", "2026-02-30", "not a date"])
def test_invalid_end_never_becomes_single_day(end):
    doc, links, structured = leads.page_document(
        event_html("2026-10-09", end), "https://example.org/puja", "en", profile=True
    )
    item = leads.screen(structured[1].candidates[0], doc, links, "california", [])
    assert item["supported_dates"] is None


@pytest.mark.parametrize(
    "literal,start,end",
    [
        ("9, 10 & 11 October 2026", "2026-10-09", "2026-10-11"),
        ("Friday, October 9 – Sunday, October 11, 2026", "2026-10-09", "2026-10-11"),
        ("2026 – October 23rd to October 25th", "2026-10-23", "2026-10-25"),
    ],
)
def test_grounded_prose_through_existing_profile_fallback(
    tmp_path, monkeypatch, literal, start, end
):
    from food_safety.structured_llm import ModelReply

    file = campaign(tmp_path, monkeypatch, f"<p>Fixture Durga Puja: {literal}</p>")
    seeds = json.loads(file.read_text())
    seeds[0].update(mode="profile", accepted_identity="Fixture Durga Puja")
    file.write_text(json.dumps(seeds))

    class ProseModel:
        def extract(self, document, schema, task, limits):
            p = document.passages[0]

            def field(value):
                return {
                    "raw_value": value,
                    "passage_id": p.passage_id,
                    "original_quote": p.original_text,
                }

            return ModelReply(
                json.dumps(
                    {
                        "completion_status": "complete",
                        "candidates": [
                            {
                                "name": field("Fixture Durga Puja"),
                                "year": field("2026"),
                                "dates": field(literal),
                            }
                        ],
                    }
                ),
                "fixture",
            )

    result = leads.run(tmp_path, file, "prose", 1, extractor=ProseModel())
    assert result["calls_this_run"] == 1
    packet = json.loads((tmp_path / ".cache/puja/campaigns/prose/review.json").read_text())
    d = packet["sources"][0]["candidates"][0]["supported_dates"]
    assert (d["start_date"], d["end_date"]) == (start, end)
    assert literal in d["evidence"]["original_quote"]


@pytest.mark.parametrize(
    "text",
    [
        "9, 11 & 12 October 2026",
        "11, 10 & 9 October 2026",
        "30 & 31 February 2026",
        "9, 10 & 11 October",
        "October 9, 2025 – October 11, 2026",
        "2025 – October 9–11, 2026",
        "Friday, October 9 – Sunday, October 11",
        "2026 – October 25th to October 23rd",
        "Durga Puja 2026",
    ],
)
def test_ambiguous_or_unsupported_prose_rejected(text):
    assert leads.explicit_dates(text) is None


def test_legacy_structured_end_retained():
    html = event_html("2026-10-09", "2026-10-11", {"address": {"addressLocality": "Newark"}})
    _, result = events(html, "https://example.org/event", "en")
    assert result.candidates[0].end_date.raw_value == "2026-10-11"


def test_canonical_records_unchanged_by_source_url_precision():
    from food_safety.puja.pipeline import load_config

    root = Path(__file__).resolve().parents[1]
    public = json.loads((root / "site/data/pandals.json").read_text())["records"]
    expected = {p["pandal_id"]: p for p in public if p["region_id"] == "california"}
    actual = {
        p.pandal_id: p.model_dump(mode="json")
        for p in load_config(root).published
        if p.region_id == "california"
    }
    assert actual == expected
