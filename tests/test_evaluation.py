import json

import pytest
from conftest import FakeFetcher, enable_policy

from food_safety.evaluation import compare_records, evaluate_corpus, prepare_corpus


def test_corpus_is_private_bounded_reused_and_unreviewed(project, policy):
    enable_policy(project, policy)
    source = (
        "<article><p>KMC food safety officials inspected restaurants in Park Street.</p></article>"
    )
    before = (project / "data/events.json").read_bytes()
    result = prepare_corpus(project, 1, FakeFetcher(source))
    assert result["corpus_articles"] == 1 and result["gold_reviewed"] == 0
    assert prepare_corpus(project, 1, FakeFetcher(AssertionError()))["reused"] == 1
    evaluation = evaluate_corpus(project)
    assert evaluation["model_calls"] == 0 and evaluation["gold_reviewed"] == 0
    assert evaluation["deterministic_candidates"] == 1
    assert (project / "data/events.json").read_bytes() == before
    report = json.loads((project / ".cache/llm_eval/evaluation.json").read_text())
    assert report["articles"][0]["deterministic_metrics"] is None
    assert report["articles"][0]["validated_shadow_metrics"] is None


def test_scoring_does_not_match_a_different_establishment():
    gold = [
        {
            "record_scope": "establishment_event",
            "fields": {
                "area": "Park Street",
                "establishment_name": "Cafe X",
                "reported_action": "inspected",
            },
        }
    ]
    assert compare_records(gold, gold)["record_precision"] == 1
    wrong = [
        {
            "record_scope": "establishment_event",
            "fields": {
                "area": "Park Street",
                "establishment_name": "Cafe Y",
                "reported_action": "inspected",
            },
        }
    ]
    assert compare_records(wrong, gold)["record_precision"] == 0
    assert compare_records([], gold)["record_precision"] is None
    assert compare_records([], gold)["record_recall"] == 0


def test_gold_is_bound_to_revision_and_story_group(project, policy):
    enable_policy(project, policy)
    prepare_corpus(project, 1, FakeFetcher("<article>Sample collected in Kolkata.</article>"))
    path = next((project / ".cache/llm_eval/corpus").glob("*.gold.json"))
    gold = json.loads(path.read_text())
    gold["source_revision_id"] = "wrong"
    path.write_text(json.dumps(gold))
    with pytest.raises(ValueError, match="gold_revision_mismatch"):
        evaluate_corpus(project)


def test_correction_in_another_passage_blocks_automatic_eligibility():
    from test_structured_extraction import EN, proposed

    from food_safety.candidates import CandidateRecord, validate_candidate
    from food_safety.documents import freeze_document

    document = freeze_document(
        f"<article><p>{EN}</p><p>Correction: this report is withdrawn.</p></article>",
        "https://example.org/fixture",
    )
    result = validate_candidate(CandidateRecord.model_validate(proposed()), document)
    assert result["decision"] == "review"
    assert "document_correction_requires_review" in result["review_reasons"]
