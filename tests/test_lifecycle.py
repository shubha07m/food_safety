import json
from datetime import timedelta

import pytest
from conftest import AT, FakeFetcher, enable_policy, load

from food_safety.build import build, lifecycle_counts
from food_safety.config import Settings
from food_safety.fetch import FetchError
from food_safety.lifecycle import availability, due, source_key
from food_safety.migrate import migrate
from food_safety.models import Event
from food_safety.pipeline import update
from food_safety.storage import save_events


def existing(project, policy, record, monkeypatch):
    enable_policy(project, policy)
    monkeypatch.setattr("food_safety.pipeline.now", lambda: AT)
    record.is_fixture = False
    save_events(project, "events", [record], AT)


@pytest.mark.parametrize("failure", [FetchError("http_403"), TimeoutError(), OSError()])
def test_transport_warns_not_suspends(project, policy, record, monkeypatch, failure):
    existing(project, policy, record, monkeypatch)
    update(project, fetcher=FakeFetcher(failure))
    row = load(project, "events")["records"][0]
    assert row["publication_status"] == "active_with_warning"
    assert row["evidence_support_status"] == "supported_as_of"
    assert load(project, "pending")["record_count"] == 0


def test_unrelated_page_change_remains_active(project, policy, record, monkeypatch, fixture_html):
    existing(project, policy, record, monkeypatch)
    update(
        project,
        fetcher=FakeFetcher(fixture_html.replace("</article>", " New weather section.</article>")),
    )
    assert load(project, "events")["records"][0]["publication_status"] == "active"


def test_transport_restores_same_identity_and_date(
    project, policy, record, monkeypatch, fixture_html
):
    existing(project, policy, record, monkeypatch)
    update(project, fetcher=FakeFetcher(FetchError("http_403")))
    monkeypatch.setattr("food_safety.pipeline.now", lambda: AT + timedelta(hours=5))
    update(project, fetcher=FakeFetcher(fixture_html))
    row = load(project, "events")["records"][0]
    assert row["publication_status"] == "active"
    assert row["first_published_at"] == record.first_published_at.isoformat().replace("+00:00", "Z")
    assert row["event_id"] == record.event_id


def test_semantic_hold_never_auto_restores(project, policy, record, monkeypatch, fixture_html):
    existing(project, policy, record, monkeypatch)
    update(project, fetcher=FakeFetcher(fixture_html.replace("was inspected", "was not inspected")))
    assert load(project, "events")["record_count"] == 0
    assert load(project, "pending")["records"][0]["publication_status"] == "needs_review"
    update(project, fetcher=FakeFetcher(fixture_html))
    assert load(project, "events")["record_count"] == 0


def test_whole_article_withdrawn(project, policy, record, monkeypatch):
    existing(project, policy, record, monkeypatch)
    update(project, fetcher=FakeFetcher("<article>This article has been withdrawn.</article>"))
    assert load(project, "pending")["records"][0]["publication_status"] == "suspended"


def test_prolonged_unavailability_archives(project, policy, record, monkeypatch):
    existing(project, policy, record, monkeypatch)
    monkeypatch.setattr("food_safety.pipeline.now", lambda: AT + timedelta(days=31))
    update(project, fetcher=FakeFetcher(TimeoutError()))
    row = load(project, "pending")["records"][0]
    assert row["publication_status"] == "archived_unverifiable"
    assert row["evidence_support_status"] == "supported_as_of"
    build(project)
    summary = json.loads((project / "site/data/lifecycle.json").read_text())
    assert summary["ever_published"] == 1 and summary["active"] == 0
    assert summary["new_last_7_days"] == 0


def test_one_check_multiple_records_and_scoped_correction(
    project, policy, record, monkeypatch, fixture_html
):
    existing(project, policy, record, monkeypatch)
    raw = json.loads(
        json.dumps(record.model_dump(mode="json")).replace("Example Kitchen", "Other Kitchen")
    )
    raw["event_id"] = "WBFS-1123456789ab"
    raw["sources"][0]["evidence_span_hash"] = ""
    second = Event.model_validate(raw)
    save_events(project, "events", [record, second], AT)

    class Counting(FakeFetcher):
        calls = 0

        def article(self, url):
            self.calls += 1
            return super().article(url)

    body = fixture_html.replace(
        "</article>",
        second.sources[0].evidence_context
        + " Correction: Other Kitchen details require review.</article>",
    )
    fetcher = Counting(body)
    update(project, fetcher=fetcher)
    assert fetcher.calls == 1
    assert [r["event_id"] for r in load(project, "events")["records"]] == [record.event_id]
    assert load(project, "pending")["records"][0]["event_id"] == second.event_id


def test_retry_counter_and_retry_after():
    checks, url = {}, "https://example.org/a"
    availability(checks, url, AT, TimeoutError())
    assert not due(checks, url, AT + timedelta(hours=3))
    assert due(checks, url, AT + timedelta(hours=4))
    availability(
        checks, url, AT + timedelta(hours=4), FetchError("http_429"), AT + timedelta(days=2)
    )
    assert not due(checks, url, AT + timedelta(days=1))
    availability(checks, url, AT + timedelta(days=8), TimeoutError())
    assert checks[source_key(url)]["review_due"]


def test_no_fake_form_link():
    assert Settings().community_submission_url is None
    for url in [
        "https://example.org/form",
        "https://docs.google.com/forms/d/e/x/edit",
        "javascript:bad",
    ]:
        with pytest.raises(ValueError):
            Settings(community_submission_url=url)
    assert Settings(community_submission_url="https://forms.gle/abc12345").community_submission_url


def test_host_circuit_breaker_stops_repeated_requests(project, policy, monkeypatch):
    policy.urls = ["https://example.org/a", "https://example.org/b", "https://example.org/c"]
    enable_policy(project, policy)
    monkeypatch.setattr("food_safety.pipeline.now", lambda: AT)

    class Failing:
        calls = 0

        def article(self, url):
            self.calls += 1
            raise FetchError("http_403")

    fetcher = Failing()
    run = update(project, fetcher=fetcher)
    assert fetcher.calls == 2
    assert run["reason_counts"]["host_circuit_open"] == 1


def test_challenge_page_is_transport_warning(project, policy, record, monkeypatch):
    existing(project, policy, record, monkeypatch)
    update(
        project,
        fetcher=FakeFetcher("<title>Just a moment</title><body>Verify you are human</body>"),
    )
    row = load(project, "events")["records"][0]
    assert row["publication_status"] == "active_with_warning"
    assert row["source_availability_reason"] == "challenge_page"


def test_migration_is_idempotent(project, policy, record, monkeypatch):
    policy.language = "en"
    existing(project, policy, record, monkeypatch)
    raw = load(project, "events")
    raw["records"][0]["sources"][0]["source_language"] = "bn"
    (project / "data/events.json").write_text(json.dumps(raw))
    migrate(project)
    first = (project / "data/events.json").read_bytes()
    migrate(project)
    assert (project / "data/events.json").read_bytes() == first
    assert load(project, "events")["records"][0]["event_id"] == record.event_id
    assert load(project, "events")["records"][0]["sources"][0]["source_language"] == "en"


def test_restoration_not_new_publication(record):
    result = lifecycle_counts([record], [], (AT + timedelta(days=20)).isoformat())
    assert result["ever_published"] == 1 and result["new_last_7_days"] == 0
