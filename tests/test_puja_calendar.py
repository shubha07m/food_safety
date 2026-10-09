from copy import deepcopy
from pathlib import Path

import pytest

from food_safety.puja.location import effective_location
from food_safety.puja.models import PandalRecord, ReviewedDates
from food_safety.puja.pipeline import load_config

ROOT = Path(__file__).resolve().parents[1]


def supported():
    return next(p for p in load_config(ROOT).published if p.pandal_id == "ca-agomoni")


def test_date_only_review_leaves_edition_location_and_publication_unchanged():
    for p in load_config(ROOT).published:
        if not p.reviewed_dates:
            continue
        assert p.edition is None
        full = p.model_dump(mode="json")
        without = {k: v for k, v in full.items() if k != "reviewed_dates"}
        for year in (2026, 2027):
            assert effective_location(full, year) == effective_location(without, year)
        assert not effective_location(full, 2026)["directions_eligible"]


@pytest.mark.parametrize("change", [
    {"start_date": "2026-02-30"}, {"end_date": "2026-10-01"},
    {"timezone": "Invalid/Zone"}, {"evidence": []},
])
def test_invalid_date_review_rejected(change):
    raw = supported().reviewed_dates.model_dump(mode="json")
    raw.update(change)
    with pytest.raises(ValueError):
        ReviewedDates.model_validate(raw)


def test_identity_attestation_cannot_support_dates():
    raw = supported().reviewed_dates.model_dump(mode="json")
    raw["evidence"][0]["evidence_kind"] = "owner_attestation"
    with pytest.raises(ValueError, match="date_review_requires_source_quote"):
        ReviewedDates.model_validate(raw)


def test_date_review_source_and_year_must_match_record():
    raw = supported().model_dump(mode="json")
    for change in ("year", "source"):
        other = deepcopy(raw)
        if change == "year":
            other["year"] = 2025
        else:
            other["reviewed_dates"]["evidence"][0]["source_url"] = "https://unrelated.example/"
        with pytest.raises(ValueError):
            PandalRecord.model_validate(other)


def test_only_three_cached_source_supported_dates_published():
    records = load_config(ROOT).published
    assert {p.pandal_id for p in records if p.reviewed_dates} == {
        "ca-agomoni", "ca-pashchimi", "ca-ankur",
    }
    for p in records:
        if p.reviewed_dates:
            assert all(e.source_revision_id for e in p.reviewed_dates.evidence)
        else:
            assert "reviewed_dates" not in p.model_dump(mode="json")
