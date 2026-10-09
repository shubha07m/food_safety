"""Date normalization is downstream of the existing grounded profile extractor."""

import pytest

from food_safety.puja.leads import PROMPT, Lead, explicit_dates, page_document, screen


@pytest.mark.parametrize("text,start,end", [
    ("October 9–11, 2026", "2026-10-09", "2026-10-11"),
    ("Oct. 16-18 2026", "2026-10-16", "2026-10-18"),
    ("October 16 to 20, 2026", "2026-10-16", "2026-10-20"),
    ("2026-12-31/2027-01-02", "2026-12-31", "2027-01-02"),
    ("2026-10-09", "2026-10-09", "2026-10-09"),
])
def test_explicit_complete_date_ranges(text, start, end):
    assert explicit_dates(text) == {"start_date": start, "end_date": end}


@pytest.mark.parametrize("text", [
    "October 9–11", "Durga Puja 2026", "10/09/2026", "October 9 or 11, 2026",
    "October 11–9, 2026", "February 30, 2026", "2026-02-30",
    "Venue: October Hall, 2026 Main St", "TBD", "October 9, 2025 and October 11, 2026",
])
def test_ambiguous_missing_year_or_malformed_dates_not_normalized(text):
    assert explicit_dates(text) is None


def screened(dates=None, year=None, venue=None):
    doc, links, _ = page_document(
        "<p>Fixture Durga Puja: October 9–11, 2026. Venue: October Hall.</p>",
        "https://example.org/puja", "en",
    )
    passage = doc.passages[0]

    def support(value):
        return {"raw_value": value, "passage_id": passage.passage_id,
                "original_quote": passage.original_text} if value else None

    candidate = Lead(name=support("Fixture Durga Puja"), dates=support(dates),
                     year=support(year), venue=support(venue))
    return screen(candidate, doc, links, "california", []), doc


def test_profile_retains_exact_quote_revision_and_url_with_normalized_dates():
    result, doc = screened("October 9–11, 2026", "2026")
    assert result["supported_dates"]["start_date"] == "2026-10-09"
    assert result["supported_dates"]["end_date"] == "2026-10-11"
    assert result["supported_dates"]["source_url"] == doc.source_url
    assert result["supported_dates"]["source_revision_id"] == doc.source_revision_id
    assert "October 9–11, 2026" in result["supported_dates"]["evidence"]["original_quote"]
    assert result["publication"] == "requires_human_approval"


@pytest.mark.parametrize("dates,year,venue", [
    (None, "2026", None), (None, "2026", "October Hall"),
    ("October 16–18, 2026", "2026", None),  # model invented date: literal check fails
    ("October 9–11", "2026", None),  # no composing a year into raw date evidence
])
def test_year_or_venue_or_unsupported_model_output_cannot_supply_date(dates, year, venue):
    result, _ = screened(dates, year, venue)
    assert result["supported_dates"] is None


def test_prompt_explicitly_forbids_inference_and_preserves_unknowns():
    assert "Never infer dates from venue information" in PROMPT
    assert "omit\ndates" in PROMPT
