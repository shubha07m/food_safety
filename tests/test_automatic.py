"""Synthetic network fixtures never enter the real research dataset."""

import hashlib
import json

import pytest
from conftest import AT, enable_policy

from food_safety.automatic import feed_candidates, page_candidates
from food_safety.build import build
from food_safety.pipeline import update
from food_safety.storage import save_events

HTML = """<head><title>Food safety inspection report</title>
<meta property="article:published_time" content="2026-01-02T12:00:00Z"></head>
<article>KMC food safety officials inspected restaurants in Kolkata.</article>"""


class DiscoveryFixture:
    def __init__(self, body=HTML, previous=None):
        self.body = body
        self.previous = previous

    def article(self, url):
        if url.endswith("/fixture") and self.previous:
            return url, self.previous
        if url.endswith("/index"):
            return url, '<a href="/new">Kolkata food safety inspection</a>'
        return url, self.body


@pytest.mark.parametrize("initial_count", [0, 1])
def test_discovered_new_record_automatically_publishes_and_builds(
    project, policy, monkeypatch, record, fixture_html, initial_count
):
    policy.urls = []
    policy.discovery_pages = ["https://example.org/index"]
    enable_policy(project, policy)
    monkeypatch.setenv("AUTO_PUBLISH", "true")
    if initial_count:
        record.is_fixture = False
        save_events(project, "events", [record], AT)
    before = json.loads((project / "data/events.json").read_text())["record_count"]
    run = update(project, fetcher=DiscoveryFixture(previous=fixture_html))
    assert run["records_published"] == 1
    build(project)
    public = json.loads((project / "site/data/events.json").read_text())
    assert public["record_count"] == before + 1
    automatic = next(r for r in public["records"] if r.get("automatic_validation"))
    assert automatic["review"] is None
    assert (
        update(project, fetcher=DiscoveryFixture(previous=fixture_html))["records_published"] == 0
    )


@pytest.mark.parametrize(
    "body",
    [
        HTML.replace("inspected", "may have inspected"),
        HTML.replace("2026-01-02T12:00:00Z", "2099-01-02T12:00:00Z"),
        HTML.replace("food safety ", ""),
        HTML.replace("Kolkata", "Unknown location"),
        HTML.replace("</article>", " Officials denied the account.</article>"),
    ],
)
def test_ambiguous_discovered_record_never_publishes(project, policy, monkeypatch, body):
    policy.urls = []
    policy.discovery_pages = ["https://example.org/index"]
    enable_policy(project, policy)
    monkeypatch.setenv("AUTO_PUBLISH", "true")
    update(project, fetcher=DiscoveryFixture(body))
    build(project)
    assert json.loads((project / "site/data/events.json").read_text())["record_count"] == 0


def test_discovery_safe_links_and_xml(policy):
    assert page_candidates('<a href="http://127.0.0.1/">food safety</a>', policy, 3) == []
    with pytest.raises(ValueError):
        feed_candidates("<!DOCTYPE x><rss/>", policy, 3)
    assert feed_candidates(
        "<rss><channel><item><title>Food safety inspection</title>"
        "<link>https://example.org/new</link></item></channel></rss>",
        policy,
        1,
    ) == ["https://example.org/new"]


def test_suspended_only_run_does_not_claim_fresh_source_scan(project, policy):
    enable_policy(project, policy)
    before = json.loads((project / "data/status.json").read_text())
    (project / "data/retired.json").write_text(
        json.dumps(
            {
                "records": [
                    {"source_url_sha256": [hashlib.sha256(policy.urls[0].encode()).hexdigest()]}
                ]
            }
        )
    )
    run = update(project, fetcher=DiscoveryFixture())
    after = json.loads((project / "data/status.json").read_text())
    assert run["sources_scanned"] == 0
    assert after.get("last_source_scan") == before.get("last_source_scan")
    assert after.get("last_successful_update") == before.get("last_successful_update")


def test_unsupported_new_candidate_is_skipped_not_network_failure(project, policy):
    enable_policy(project, policy)
    run = update(project, fetcher=DiscoveryFixture("<article>No relevant event.</article>"))
    assert run["records_published"] == 0
    assert run["records_rejected"] == 1
    assert run["errors"] == 0


def test_discovery_size_cap_does_not_raise_article_cap():
    from food_safety.config import Settings

    cfg = Settings()
    assert cfg.max_discovery_response_bytes == 1048576
    assert cfg.max_response_bytes == 524288
    with pytest.raises(ValueError):
        Settings(max_discovery_response_bytes=1048577)
