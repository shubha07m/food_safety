import http.client
import json
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest

from food_safety.puja.approvals import close_published, publish_approved, submit_approval
from food_safety.puja.intake import submission_seeds
from food_safety.puja.pipeline import build_public, load_config
from food_safety.puja.review_queue import (
    candidate_id,
    candidates,
    compile_record,
    issue_body,
    parse_issue_body,
)
from food_safety.puja.review_server import handler, render

ROOT = Path(__file__).resolve().parents[1]


def project(tmp_path):
    folder = tmp_path / "config"
    folder.mkdir()
    for name in (
        "regions.yml",
        "puja.yml",
        "puja-california.yml",
        "puja-london.yml",
        "puja-toronto.yml",
        "puja-melbourne.yml",
    ):
        shutil.copy(ROOT / "config" / name, folder / name)
    return tmp_path


def fact(value, quote):
    return {"value": value, "evidence": {"passage_id": "P001", "original_quote": quote}}


def candidate():
    quote = "River Durga Puja 2026, London, 17 October 2026, River Hall, 1 River Road"
    source = "https://example.org/puja-2026"
    return {
        "candidate_id": candidate_id("london", source, "River Durga Puja"),
        "name": "River Durga Puja",
        "region": "london",
        "source_url": source,
        "source_title": "River organizer announcement",
        "source_revision": "a" * 64,
        "monitor_revision": "b" * 64,
        "source_type": "organizer",
        "fields": {
            "name": fact("River Durga Puja", quote),
            "locality": fact("London", quote),
            "year": fact("2026", quote),
            "start_date": fact("2026-10-17", "2026-10-17"),
            "venue": fact("River Hall", quote),
            "address": fact("1 River Road", quote),
        },
        "summaries": {
            "about": [
                {
                    "text": "A community Puja in London.",
                    "support": [fact("River Durga Puja", quote)],
                }
            ],
            "programme": [
                {"text": "Community music on 17 October.", "support": [fact("2026", quote)]}
            ],
        },
        "duplicate_ids": [],
        "same_source_listing_ids": [],
        "warnings": ["event_year_relationship_requires_review"],
        "proposed_tier": "current_edition_review_candidate",
        "map_eligibility": "not_reviewed",
        "review_state": "pending",
    }


def test_candidate_id_and_two_approval_tiers(tmp_path):
    root = project(tmp_path)
    item = candidate()
    assert candidate_id("london", item["source_url"], item["name"]) == item["candidate_id"]
    at = datetime(2026, 9, 24, tzinfo=UTC)
    source_listed = compile_record(root, item, "source_listed", at=at)
    assert source_listed["record"]["edition"] is None
    assert source_listed["record"]["about"]["text"] == "A community Puja in London."
    assert source_listed["record"]["official_links"][0]["kind"] == "website"
    reviewed = compile_record(root, item, "current_edition_reviewed", at=at)
    edition = reviewed["record"]["edition"]
    assert edition["year"] == 2026 and edition["confirmed"]
    assert edition["location"]["venue"] == "River Hall"
    assert edition["location"]["latitude"] is None
    assert len(edition["programme_notes"]) == 1
    assert reviewed["source"]["reviewed_revision"] == "b" * 64
    assert parse_issue_body(issue_body(reviewed)) == reviewed
    with pytest.raises(ValueError, match="current_year_evidence_required"):
        compile_record(
            root,
            item | {"fields": item["fields"] | {"year": None}},
            "current_edition_reviewed",
            at=at,
        )


def test_duplicate_and_unsupported_facts_block_approval(tmp_path):
    root = project(tmp_path)
    item = candidate()
    item["duplicate_ids"] = ["london-camden", "london-bcsc"]
    with pytest.raises(ValueError, match="ambiguous_existing_identity"):
        compile_record(root, item, "source_listed")


def test_known_source_approval_reuses_monitor_entry(tmp_path):
    root = project(tmp_path)
    item = candidate()
    item["region"] = "california"
    item["source_url"] = "https://agomoni.org/durgapuja-2026/"
    item["candidate_id"] = candidate_id(item["region"], item["source_url"], item["name"])
    item["fields"]["locality"] = fact("San Ramon", "San Ramon")
    payload = compile_record(root, item, "source_listed")
    assert payload["source"]["source_id"] == "ca-agomoni"
    assert payload["source"]["reviewed_revision"] == "b" * 64
    assert parse_issue_body(issue_body(payload)) == payload
    item["duplicate_ids"] = []
    item["fields"]["locality"] = None
    with pytest.raises(ValueError, match="identity_region_evidence_incomplete"):
        compile_record(root, item, "source_listed")


def test_publication_skips_bad_issue_and_commits_only_approved(tmp_path):
    root = project(tmp_path)
    value = compile_record(root, candidate(), "source_listed", at=datetime(2026, 9, 24, tzinfo=UTC))
    issue = {
        "number": 40,
        "title": "Puja approval " + value["candidate_id"],
        "body": issue_body(value),
        "user": {"login": "shubha07m"},
    }
    bad = {
        "number": 41,
        "title": "Puja approval pc-invalid",
        "body": "invalid",
        "user": {"login": "shubha07m"},
    }
    untrusted = {
        "number": 42,
        "title": issue["title"],
        "body": issue["body"],
        "user": {"login": "someone-else"},
    }
    closed = []

    def api(method, endpoint, payload=None):
        if method == "GET":
            return [bad, issue, untrusted]
        closed.append((endpoint, payload))
        return {}

    first = publish_approved(root, api=api)
    assert first["approved_added"] == 1 and first["invalid"][0]["issue_number"] == 41
    assert load_config(root).published[-1].pandal_id == value["record"]["pandal_id"]
    assert build_public(root)["record_count"] == 236
    assert publish_approved(root, api=api)["approved_added"] == 0
    assert close_published(root, api=api)["closed"] == 1
    assert closed == [("repos/shubha07m/food_safety/issues/40", {"state": "closed"})]


def test_approval_listing_outage_does_not_change_catalog(tmp_path):
    root = project(tmp_path)

    def unavailable(*_args):
        raise RuntimeError("network_unavailable")

    result = publish_approved(root, api=unavailable)
    assert result["sync"] == "unavailable"
    assert not (root / "config/puja-approved.json").exists()
    assert load_config(root).published[-1]


def test_approval_transport_requires_owner_and_keeps_contact_out(tmp_path):
    value = compile_record(project(tmp_path), candidate(), "source_listed")
    calls = []

    def api(method, endpoint, payload=None):
        calls.append((method, endpoint, payload))
        return {"login": "shubha07m"} if endpoint == "user" else {"number": 7}

    assert submit_approval(value, api=api) == 7
    assert calls[-1][2]["body"].startswith("<!-- foodpath-puja-approval-v1 -->")
    with pytest.raises(ValueError, match="github_owner_login_required"):
        submit_approval(value, api=lambda *_: {"login": "other"})


def test_suggestion_ingest_keeps_contact_and_untrusted_text_out():
    body = (
        "### Puja or organizer name\nRiver Puja\n\n### Region\nLondon region\n\n"
        "### City or locality\nLondon\n\n### Official or event URL\n"
        "https://example.org/event\n\n### Contact email\nprivate@example.org\n"
    )
    rows = submission_seeds(
        api=lambda *_: [
            {"number": 8, "title": "[Puja suggestion] River", "body": body},
            {"number": 9, "title": "Puja approval pc-other", "body": body},
        ]
    )
    assert rows == [
        {
            "region": "london",
            "url": "https://example.org/event",
            "origin": "public_suggestion",
            "submission_issue": 8,
        }
    ]
    assert "private@example.org" not in json.dumps(rows)


def test_local_review_http_and_decision_persistence(tmp_path):
    from http.server import ThreadingHTTPServer

    root = project(tmp_path)
    item = candidate()
    item["name"] = "<River Puja>"
    item["fields"]["name"] = fact("<River Puja>", "<River Puja> in London")
    packet = {k: v for k, v in item.items() if k not in {"candidate_id", "review_state"}}
    campaign = root / ".cache/puja/campaigns/example"
    campaign.mkdir(parents=True)
    (campaign / "review.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "url": item["source_url"],
                        "region": "london",
                        "status": "screened",
                        "source_title": item["source_title"],
                        "candidates": [packet],
                    }
                ]
            }
        )
    )
    assert "&lt;River Puja&gt;" in render(root, "token")
    sent = []

    def submit(payload):
        sent.append(payload)
        return 9

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(root, "token", submit=submit))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port)
        form = urlencode(
            {
                "token": "token",
                "candidate_id": candidates(root)[0]["candidate_id"],
                "revision": item["source_revision"],
                "action": "defer",
            }
        )
        connection.request(
            "POST",
            "/decision",
            form,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": f"http://127.0.0.1:{server.server_port}",
            },
        )
        assert connection.getresponse().status == 303
        assert candidates(root)[0]["review_state"] == "defer"
        # A changed source revision reopens the editorial choice.
        raw = json.loads((campaign / "review.json").read_text())
        raw["sources"][0]["candidates"][0]["source_revision"] = "c" * 64
        (campaign / "review.json").write_text(json.dumps(raw))
        form = urlencode(
            {
                "token": "token",
                "candidate_id": candidates(root)[0]["candidate_id"],
                "revision": "c" * 64,
                "action": "source_listed",
            }
        )
        connection.request(
            "POST",
            "/decision",
            form,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": f"http://127.0.0.1:{server.server_port}",
            },
        )
        assert connection.getresponse().status == 303
        assert candidates(root)[0]["review_state"] == "approved"
        assert sent[0]["record"]["about"]["text"] == "A community Puja in London."
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
