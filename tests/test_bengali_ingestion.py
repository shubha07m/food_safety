import pytest
from conftest import FakeFetcher, enable_policy, load

from food_safety.dedupe import area_key
from food_safety.pipeline import update

SENTENCE = "কলকাতা পুরসভার খাদ্য সুরক্ষা আধিকারিকরা পার্ক স্ট্রিট এলাকায় রেস্তোরাঁ পরিদর্শন করেছেন।"


def test_bilingual_locality_overlap_does_not_change_original():
    assert area_key("পার্ক স্ট্রিট") == area_key("Park Street")
    assert area_key("কলকাতা") == area_key("Kolkata")


@pytest.mark.parametrize("ambiguous", [False, True])
def test_bengali_admission(project, policy, monkeypatch, ambiguous):
    enable_policy(project, policy)
    monkeypatch.setenv("AUTO_PUBLISH", "true")
    sentence = SENTENCE.replace("পরিদর্শন করেছেন", "পরিদর্শন করতে পারেন") if ambiguous else SENTENCE
    html = (
        "<head><title>খাদ্য সুরক্ষা পরিদর্শন</title>"
        '<meta property="article:published_time" content="2026-01-02"></head><article>'
        + sentence
        + "</article>"
    )
    update(project, fetcher=FakeFetcher(html))
    data = load(project, "events")
    assert data["record_count"] == (0 if ambiguous else 1)
    if not ambiguous:
        row = data["records"][0]
        assert row["sources"][0]["evidence_quote"] == SENTENCE
        assert row["sources"][0]["source_language"] == "bn"
        assert row["reported_fact"]["area"] == "পার্ক স্ট্রিট"
