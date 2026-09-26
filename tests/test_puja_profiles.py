import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from food_safety.config import settings
from food_safety.puja import leads
from food_safety.puja.location import effective_location
from food_safety.puja.models import Edition, EditionLocation, OfficialLink, SourcedText
from food_safety.puja.pipeline import load_config
from food_safety.structured_llm import ModelReply

ROOT = Path(__file__).resolve().parents[1]


def test_shared_effective_location_contract():
    for case in json.loads((ROOT / "tests/fixtures/puja_locations.json").read_text()):
        result = effective_location(case["record"], 2026)
        assert {k: result[k] for k in case["expected"]} == case["expected"], case["label"]


def test_edition_location_atomic_override_and_year_boundary():
    p = next(p for p in load_config(ROOT).published if p.edition).model_dump(mode="json")
    assert effective_location(p, 2026)["directions_eligible"]
    assert not effective_location(p, 2027)["map_eligible"]
    p["edition"]["location"] = None
    assert not effective_location(p, 2026)["map_eligible"]
    p["edition"] = None
    assert effective_location(p, 2026)["status"] == "last_known"
    assert not effective_location(p, 2026)["directions_eligible"]
    p["coordinate_precision"] = "neighborhood"
    assert effective_location(p, 2026)["map_eligible"]
    assert not effective_location(p, 2026)["near_me_eligible"]


def test_profile_evidence_and_programme_limits():
    raw = next(p for p in load_config(ROOT).published if p.edition).edition.model_dump(mode="json")
    note = {"title": "Programme", "text": "Fixture only", "evidence": raw["evidence"]}
    assert Edition.model_validate(raw | {"programme_notes": [note]}).programme_notes
    with pytest.raises(ValueError):
        Edition.model_validate(raw | {"programme_notes": [note] * 4})
    for cls, fields in [
        (SourcedText, {"text": "unsupported"}),
        (OfficialLink, {"kind": "facebook", "url": "https://example.org"}),
    ]:
        with pytest.raises(ValueError):
            cls.model_validate(fields)
    location = raw["location"]
    for patch in (
        {"longitude": None},
        {"coordinate_source": None},
        {"coordinate_source": "https://maps.google.com"},
        {"evidence": []},
    ):
        with pytest.raises(ValueError):
            EditionLocation.model_validate(location | patch)


def test_food_uses_edition_anchor(monkeypatch):
    from food_safety.food_pois import pipeline

    p = next(p for p in load_config(ROOT).published if p.edition)
    moved = p.model_copy(deep=True)
    moved.edition.location.latitude += 0.001
    monkeypatch.setattr(
        "food_safety.puja.pipeline.load_config", lambda root: SimpleNamespace(published=[moved])
    )
    result = pipeline.regional_pandals(ROOT, p.region_id)
    assert result[0].latitude == moved.edition.location.latitude
    assert result[0].latitude != moved.latitude


def campaign(tmp_path, monkeypatch, html="<main><p>Fixture Durga Puja in London</p></main>"):
    monkeypatch.setattr(leads, "get_region", lambda root, region: SimpleNamespace(region_id=region))
    monkeypatch.setattr(leads, "settings_for", lambda root: settings(ROOT))
    monkeypatch.setattr(leads, "load_config", lambda root: SimpleNamespace(published=[]))

    class Fetcher:
        def __init__(self, *args, reserve, **kwargs):
            self.reserve = reserve

        def article(self, url):
            self.reserve()
            return url, html

    monkeypatch.setattr(leads, "CampaignFetcher", Fetcher)
    monkeypatch.setattr(leads.time, "sleep", lambda _: None)
    file = tmp_path / "seeds.json"
    file.write_text(json.dumps([{"region": "london", "url": "https://example.org/puja"}]))
    return file


class Model:
    calls = 0
    fail = False

    def extract(self, document, schema, task, limits):
        self.calls += 1
        if self.fail:
            raise RuntimeError("fixture failure")
        passage = next(p for p in document.passages if "Fixture Durga Puja" in p.original_text)
        result = {
            "completion_status": "complete",
            "candidates": [
                {
                    "name": {
                        "raw_value": "Fixture Durga Puja",
                        "passage_id": passage.passage_id,
                        "original_quote": passage.original_text,
                    }
                }
            ],
        }
        return ModelReply(json.dumps(result), "fixture", 10, 5)


def test_manual_prose_extraction_cache_and_private_only(tmp_path, monkeypatch):
    file = campaign(tmp_path, monkeypatch)
    model = Model()
    assert leads.run(tmp_path, file, "test", 5, True)["max_model_attempts_this_run"] == 5
    assert not (tmp_path / ".cache").exists()
    first = leads.run(tmp_path, file, "test", 1, extractor=model)
    assert first["candidates"] == 1 and first["ledger"]["attempts"] == 1
    second = leads.run(tmp_path, file, "test", 1, extractor=model)
    assert second["cache_hits"] == 1 and second["calls_this_run"] == 0
    assert model.calls == 1
    assert not (tmp_path / "site").exists() and not (tmp_path / "config").exists()
    packet = json.loads((tmp_path / second["review_packet"]).read_text())
    assert packet["publication"] == "requires_human_approval"
    candidate = packet["sources"][0]["candidates"][0]
    assert candidate["fields"]["venue"] is None
    assert candidate["map_eligibility"] == "not_reviewed"


def test_attempts_count_failure_and_hard_ceiling(tmp_path, monkeypatch):
    file = campaign(tmp_path, monkeypatch)
    model = Model()
    model.fail = True
    first = leads.run(tmp_path, file, "test", 1, extractor=model)
    assert first["ledger"]["attempts"] == 1 and first["ledger"]["successes"] == 0
    path = tmp_path / ".cache/puja/campaigns/test/ledger.json"
    state = json.loads(path.read_text())
    state["attempts"] = 20
    path.write_text(json.dumps(state))
    assert leads.run(tmp_path, file, "test", 99, extractor=model)["calls_this_run"] == 0
    assert model.calls == 1


def test_structured_leads_bypass_model_and_one_hop_is_not_fetched(tmp_path, monkeypatch):
    event = {
        "@type": "Event",
        "name": "Fixture Durga Puja",
        "location": {"address": {"addressLocality": "London"}},
    }
    html = (
        '<script type="application/ld+json">'
        + json.dumps(event)
        + '</script><a href="https://example.org/other">Other</a>'
    )
    file = campaign(tmp_path, monkeypatch, html)
    seeds = json.loads(file.read_text())
    seeds[0]["content_selector"] = None  # SourceSpec serializes this optional field as null.
    seeds[0]["refresh_revision"] = None
    file.write_text(json.dumps(seeds))
    model = Model()
    model.fail = True
    result = leads.run(tmp_path, file, "test", 5, extractor=model)
    assert result["candidates"] == 1 and model.calls == 0
    assert result["ledger"]["http_attempts"] == 1


def test_structured_profile_keeps_supported_edition_without_model(tmp_path, monkeypatch):
    event = {
        "@type": "Event",
        "name": "Fixture Durga Puja",
        "startDate": "2026-10-17",
        "location": {
            "name": "Fixture Hall",
            "address": {"addressLocality": "London", "streetAddress": "1 Fixture Street"},
        },
    }
    html = '<script type="application/ld+json">' + json.dumps(event) + "</script>"
    file = campaign(tmp_path, monkeypatch, html)
    seeds = json.loads(file.read_text())
    seeds[0]["mode"] = "profile"
    seeds[0]["accepted_identity"] = "Fixture Durga Puja"
    seeds[0]["candidate_name"] = "Fixture Durga Puja"
    file.write_text(json.dumps(seeds))
    model = Model()
    model.fail = True
    result = leads.run(tmp_path, file, "structured-profile", 5, extractor=model)
    assert result["candidates"] == 1 and model.calls == 0
    packet = json.loads(
        (tmp_path / ".cache/puja/campaigns/structured-profile/review.json").read_text()
    )
    fields = packet["sources"][0]["candidates"][0]["fields"]
    assert fields["year"]["value"] == "2026"
    assert fields["start_date"]["value"] == "2026-10-17"
    assert fields["venue"]["value"] == "Fixture Hall"


def test_candidate_nfc_evidence_duplicates_and_invalid_urls():
    doc, links, _ = leads.page_document(
        "<main><p>Café Durga Puja, London</p></main>", "https://example.org", "en"
    )
    p = doc.passages[0]
    candidate = leads.Lead(
        name={
            "raw_value": "Café Durga Puja",
            "passage_id": p.passage_id,
            "original_quote": p.original_text,
        }
    )
    known = [
        SimpleNamespace(
            pandal_id="known",
            region_id="london",
            name="Cafe\u0301 Durga Puja",
            aliases=[],
            sources=[],
        )
    ]
    assert leads.screen(candidate, doc, links, "london", known)["duplicate_ids"] == ["known"]
    for url in [
        "http://localhost/x",
        "https://127.0.0.1/",
        "file:///tmp/source",
        "https://user:pass@example.org",
    ]:
        with pytest.raises(ValueError):
            leads.canonical(url)
    candidate.name.raw_value = "Invented"
    with pytest.raises(ValueError):
        leads.screen(candidate, doc, links, "london", [])


def test_unaccepted_profile_and_seed_count_rejected(tmp_path, monkeypatch):
    file = campaign(tmp_path, monkeypatch)
    row = {"region": "london", "url": "https://example.org", "mode": "profile"}
    file.write_text(json.dumps([row]))
    with pytest.raises(ValueError, match="accepted_identity"):
        leads.run(tmp_path, file, "test", 1)
    file.write_text(json.dumps([row] * 41))
    with pytest.raises(ValueError, match="40"):
        leads.run(tmp_path, file, "test", 1)


def test_lead_schema_is_compact_and_profile_fields_are_evidence_required():
    properties = leads.LeadOnly.model_json_schema()["properties"]
    assert not {"about", "programme", "venue", "dates"}.intersection(properties)
    assert {"name", "organizer", "locality", "event_url"}.issubset(properties)


def test_date_year_link_and_timezone_screening():
    doc, links, _ = leads.page_document(
        "<main><p>Fixture Puja 2026. Date 2025-10-17. End 2025-10-16. Zone Bad/Zone.</p>"
        '<a href="https://example.org/social">Official community account</a></main>',
        "https://example.org",
        "en",
    )
    passage = doc.passages[0]

    def support(value):
        return {
            "raw_value": value,
            "passage_id": passage.passage_id,
            "original_quote": passage.original_text,
        }

    candidate = leads.Lead(
        name=support("Fixture Puja"),
        year=support("2026"),
        start_date=support("2025-10-17"),
        end_date=support("2025-10-16"),
        timezone=support("Bad/Zone"),
    )
    item = leads.screen(candidate, doc, links, "london", [])
    assert {"date_range_conflict", "date_year_conflict", "timezone_invalid"}.issubset(
        item["warnings"]
    )
    assert item["fields"]["timezone"] is None and item["fields"]["end_date"] is None
    assert item["publication"] == "requires_human_approval"


def test_provider_failure_stops_remaining_batch(tmp_path, monkeypatch):
    from food_safety.structured_llm import ModelFailure

    file = campaign(tmp_path, monkeypatch)
    file.write_text(
        json.dumps([{"region": "london", "url": f"https://example.org/{i}"} for i in range(3)])
    )

    class FailedModel:
        def extract(self, *args):
            raise ModelFailure("provider_http_402_resource_exhausted")

    result = leads.run(tmp_path, file, "test", 5, extractor=FailedModel())
    assert result["calls_this_run"] == 1
    assert result["ledger"]["last_model_error"] == "provider_http_402_resource_exhausted"


def test_http_budget_stops_before_next_fetch(tmp_path, monkeypatch):
    file = campaign(tmp_path, monkeypatch)
    folder = tmp_path / ".cache/puja/campaigns/test"
    folder.mkdir(parents=True)
    (folder / "ledger.json").write_text(
        json.dumps({"attempts": 0, "successes": 0, "http_attempts": 120})
    )
    result = leads.run(tmp_path, file, "test", 1, extractor=Model())
    assert result["ledger"]["http_attempts"] == 120
    assert result["calls_this_run"] == 0
