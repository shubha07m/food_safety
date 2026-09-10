import csv
import json

import httpx
from conftest import FixtureLLM, enable_policy, model_candidate, model_payload

from food_safety.community import import_approved_csv
from food_safety.discovery import BraveSearch, page_candidates, sitemap_candidates
from food_safety.pipeline import update


class MultiFetcher:
    def __init__(self, article):
        self.article_body = article
        self.calls = []

    def article(self, url):
        self.calls.append(url)
        if url.endswith("/index"):
            return url, (
                '<a href="/new">খাদ্য সুরক্ষা কলকাতা রেস্তোরাঁ অভিযান</a>'
                '<a href="/new">duplicate food safety inspection</a>'
            )
        return url, self.article_body


def _html(text):
    return (
        "<head><title>Food safety inspection report</title>"
        '<meta property="article:published_time" content="2026-01-02"></head>'
        f"<article>{text}</article>"
    )


def test_sitemap_and_bengali_index_discovery(policy):
    body = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:news="http://www.google.com/schemas/sitemap-news/0.9"><url>'
        "<loc>https://example.org/report</loc><news:news><news:title>"
        "খাদ্য সুরক্ষা কলকাতা অভিযান</news:title></news:news></url></urlset>"
    )
    assert sitemap_candidates(body, policy, 5) == ["https://example.org/report"]
    assert page_candidates('<a href="/bn">খাদ্য সুরক্ষা কলকাতা অভিযান</a>', policy, 5) == [
        "https://example.org/bn"
    ]


def test_duplicate_discovery_url_fetched_once(project, policy, monkeypatch):
    policy.urls = []
    policy.discovery_pages = ["https://example.org/index"]
    enable_policy(project, policy)
    monkeypatch.setenv("AUTO_PUBLISH", "true")
    fetcher = MultiFetcher(_html("KMC food safety officials inspected restaurants in Kolkata."))
    update(project, fetcher=fetcher)
    assert fetcher.calls.count("https://example.org/new") == 1


def test_aggregate_and_named_events_are_separate_and_linked(project, policy, monkeypatch):
    policy.urls = []
    policy.discovery_pages = ["https://example.org/index"]
    enable_policy(project, policy)
    monkeypatch.setenv("AUTO_PUBLISH", "true")
    body = _html(
        "KMC food safety officials inspected 120 establishments across West Bengal. "
        "KMC food safety officials visited Alpha Cafe and Beta Cafe in Kolkata."
    )
    aggregate = "KMC food safety officials inspected 120 establishments across West Bengal."
    named = "KMC food safety officials visited Alpha Cafe and Beta Cafe in Kolkata."
    candidates = [
        model_candidate(
            aggregate,
            "West Bengal",
            "KMC food safety officials",
            "inspected",
            scope="statewide_operation",
        ),
        model_candidate(
            named,
            "Kolkata",
            "KMC food safety officials",
            "visited",
            candidate_id="C2",
            scope="establishment_event",
            name="Alpha Cafe",
        ),
        model_candidate(
            named,
            "Kolkata",
            "KMC food safety officials",
            "visited",
            candidate_id="C3",
            scope="establishment_event",
            name="Beta Cafe",
        ),
    ]
    update(
        project, fetcher=MultiFetcher(body), llm_extractor=FixtureLLM(model_payload(*candidates))
    )
    rows = json.loads((project / "data/events.json").read_text())["records"]
    assert {row["record_scope"] for row in rows} == {
        "statewide_operation",
        "establishment_event",
    }
    assert len(rows) == 3
    assert all(len(row["related_record_ids"]) == 2 for row in rows)


def test_blocked_source_does_not_stop_other_candidate(project, policy, monkeypatch):
    policy.urls = []
    policy.discovery_pages = ["https://example.org/index"]
    enable_policy(project, policy)
    monkeypatch.setenv("AUTO_PUBLISH", "true")
    text = "KMC food safety officials inspected restaurants in Kolkata."
    update(
        project,
        fetcher=MultiFetcher(_html(text)),
        llm_extractor=FixtureLLM(
            model_payload(
                model_candidate(text, "Kolkata", "KMC food safety officials", "inspected")
            )
        ),
    )
    assert json.loads((project / "data/events.json").read_text())["record_count"] == 1


def test_search_api_only_returns_configured_domains(policy, monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fixture")

    def handler(request):
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {"url": "https://example.org/food-safety"},
                        {"url": "https://outside.example/report"},
                    ]
                }
            },
            request=request,
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    found = BraveSearch([policy], max_queries=1, client=client).discover(10)
    assert [url for _, url in found] == ["https://example.org/food-safety"]
    client.close()


def test_community_import_discards_private_fields(tmp_path, policy):
    source = tmp_path / "responses.csv"
    with source.open("w", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["public source URL", "submission type", "email", "short note"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "public source URL": "https://example.org/report",
                "submission type": "inspection / safety evidence",
                "email": "private@example.net",
                "short note": "private note",
            }
        )
    destination = tmp_path / "leads.json"
    assert import_approved_csv(source, destination, [policy]) == 1
    rendered = destination.read_text()
    assert "private@example.net" not in rendered
    assert "private note" not in rendered
    assert set(json.loads(rendered)["leads"][0]) == {"source_url", "submission_type"}
