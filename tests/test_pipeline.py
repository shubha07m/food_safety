import json
from pathlib import Path

import httpx
import pytest
from conftest import AT, FakeFetcher, enable_policy, load

from food_safety.extract import deterministic_extract
from food_safety.llm import DisabledVLM, OpenAICompatible
from food_safety.pipeline import review_record, update
from food_safety.storage import save_events


def test_fixture_pipeline_pending(project, policy, fixture_html):
    enable_policy(project, policy)
    run = update(project, max_articles=1, fetcher=FakeFetcher(fixture_html))
    assert run["records_pending"] == 1
    assert load(project, "events")["record_count"] == 0
    assert load(project, "pending")["records"][0]["reported_fact"]["establishment_name"] is None
    assert load(project, "status")["last_successful_update"]


def test_unchanged_rescan_idempotent(project, policy, fixture_html):
    enable_policy(project, policy)
    update(project, fetcher=FakeFetcher(fixture_html))
    update(project, fetcher=FakeFetcher(fixture_html))
    assert load(project, "pending")["record_count"] == 1


def test_broken_source_rejected(project, policy):
    enable_policy(project, policy)
    update(project, fetcher=FakeFetcher(OSError("secret text never logged")))
    assert load(project, "rejected")["record_count"] == 1
    assert load(project, "events")["record_count"] == 0
    assert "secret text" not in (project / "data/rejected.json").read_text()


def test_discovery_source_not_fetched(project, policy):
    policy.tier = "discovery"
    enable_policy(project, policy)
    run = update(project, fetcher=FakeFetcher(AssertionError("must never fetch")))
    assert run["urls_considered"] == 0


def test_explicit_review_publishes(project, policy, fixture_html, record):
    enable_policy(project, policy)
    # Test-only simulation; production fixtures remain prohibited.
    record.is_fixture = False
    review_record(
        project,
        record.model_dump(mode="json"),
        "test-maintainer",
        "Context checked",
        fetcher=FakeFetcher(fixture_html),
    )
    assert load(project, "events")["record_count"] == 1


@pytest.mark.parametrize(
    "html", [OSError("unavailable"), "<article>Correction: withdrawn.</article>"]
)
def test_previous_public_record_suspended(project, policy, record, html):
    enable_policy(project, policy)
    record.is_fixture = False
    save_events(project, "events", [record], AT)
    update(project, fetcher=FakeFetcher(html))
    assert load(project, "events")["record_count"] == 0
    assert load(project, "pending")["record_count"] == 1
    assert list((project / "data/history" / record.event_id).glob("*.json"))


def test_corrected_article_fails_closed():
    with pytest.raises(ValueError, match="source_update"):
        deterministic_extract("Correction: this establishment was inspected on another date.")


@pytest.mark.parametrize("name", ["multiple", "ambiguous"])
def test_ambiguous_articles_not_attributed(name):
    from food_safety.extract import article_text

    html = (Path(__file__).parent / "fixtures" / f"{name}.html").read_text()
    fields = deterministic_extract(article_text(html)[1])
    assert set(fields) == {"reported_observation"}


def test_llm_off_by_default(project):
    with pytest.raises(ValueError, match="enable_llm"):
        update(project, use_llm=True)


def test_llm_mock_and_budget(monkeypatch):
    for name, val in {
        "BASE_URL": "https://example.org/v1",
        "MODEL": "fixture-model",
        "PROVIDER": "fixture-provider",
        "API_KEY": "test-only",
    }.items():
        monkeypatch.setenv("FOOD_LLM_" + name, val)
    content = "Inspectors collected samples."
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"content": json.dumps({"reported_observation": content})}}
                    ]
                },
                request=request,
            )
        )
    )
    llm = OpenAICompatible(max_calls=1, client=client)
    assert llm.extract(content)["reported_observation"] == content
    with pytest.raises(ValueError, match="budget"):
        llm.extract(content)
    client.close()


def test_vlm_disabled():
    with pytest.raises(ValueError, match="disabled"):
        DisabledVLM().extract_image("https://example.org/fixture.png")
