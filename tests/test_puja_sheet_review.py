import json
from datetime import UTC, datetime

import pytest
from test_puja_approvals import candidate, project

from food_safety.puja import intake, sheets
from food_safety.puja.approvals import queue_approval, resume_approvals, submit_approval
from food_safety.puja.queue_store import STORE, ingest_responses, read
from food_safety.puja.review_queue import automatic_record, candidates, save_decision
from food_safety.puja.review_server import render


def response(**changes):
    return {
        "Timestamp": "2026-09-26 10:00:00",
        "Puja / organizer name": "River Puja",
        "City / region": "London",
        "Official organizer or event URL": "https://example.org/puja",
        "Additional note": "private note",
        "Contact email": "must-not-retain@example.org",
        **changes,
    }


def test_sync_candidate_first_idempotent_and_only_two_buttons(tmp_path):
    root = project(tmp_path)
    assert "1 new" in sheets.sync(root, reader=lambda _: [response()])
    assert "0 new" in sheets.sync(root, reader=lambda _: [response()])
    item = candidates(root)[0]
    assert not item["fields"]
    text = (root / STORE).read_text()
    assert "must-not-retain" not in text and "private note" not in text
    html = render(root, "nonce")
    assert html.count('name="action"') == 2
    assert ">APPROVE<" in html and ">REJECT<" in html
    assert "Approve reviewed" not in html and "Defer" not in html
    assert " disabled" not in html


def test_basic_approval_is_honest_without_fake_page_evidence(tmp_path):
    root = project(tmp_path)
    ingest_responses(root, [response()])
    value = automatic_record(root, candidates(root)[0])
    assert value["tier"] == "source_listed"
    assert value["record"]["edition"] is None
    assert value["record"]["latitude"] is None
    assert value["record"]["sources"][0]["evidence_kind"] == "owner_attestation"
    assert not value["record"]["official_links"]


def test_tier_derivation_requires_event_attached_year(tmp_path):
    root = project(tmp_path)
    item = candidate()
    now = datetime(2026, 9, 26, tzinfo=UTC)
    assert automatic_record(root, item, at=now)["tier"] == "current_edition_reviewed"
    item["fields"]["year"]["evidence"]["original_quote"] = "Copyright 2026"
    assert automatic_record(root, item, at=now)["tier"] == "source_listed"
    item["warnings"].append("date_year_conflict")
    assert automatic_record(root, item, at=now)["record"]["edition"] is None


@pytest.mark.parametrize("decision", ["approved", "reject"])
def test_decisions_survive_reorder_repetition_and_changed_response(tmp_path, decision):
    root = project(tmp_path)
    ingest_responses(root, [response()])
    item = candidates(root)[0]
    save_decision(root, item, decision)
    ingest_responses(root, [response(Timestamp="new timestamp"), response()])
    assert len(candidates(root)) == 1
    assert candidates(root)[0]["review_state"] == decision
    ingest_responses(root, [response(**{"Additional note": "edited private note"})])
    assert len(candidates(root)) == 1
    assert candidates(root)[0]["review_state"] == decision


@pytest.mark.parametrize("url", ["file:///tmp/foo", "http://localhost/x", "http://10.0.0.1/x"])
def test_bad_url_retained_never_fetched_or_linked(tmp_path, url):
    root = project(tmp_path)
    ingest_responses(root, [response(**{"Official organizer or event URL": url})])
    item = candidates(root)[0]
    assert item["url_usable"] is False
    assert "Source not automatically readable" in render(root, "token")
    assert f'href="{url}"' not in render(root, "token")
    with pytest.raises(ValueError):
        automatic_record(root, item)


def test_sheet_failure_still_renders_private_queue(tmp_path):
    root = project(tmp_path)
    ingest_responses(root, [response()])

    def unavailable(_):
        raise RuntimeError("provider detail must not appear")

    notice = sheets.sync(root, reader=unavailable)
    assert "using local queue" in notice
    assert "provider detail" not in notice
    assert "River Puja" in render(root, "token", notice)


def test_enrichment_failure_once_and_candidate_kept(tmp_path, monkeypatch):
    root = project(tmp_path)
    ingest_responses(root, [response()])
    calls = []

    def unavailable(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("unavailable")

    monkeypatch.setattr(intake, "run", unavailable)
    with pytest.raises(RuntimeError):
        intake.prepare(root)
    assert "River Puja" in render(root, "token")
    assert intake.prepare(root)["seeds"] == 0
    assert len(calls) == 1


def test_frozen_approval_retries_without_second_owner_action(tmp_path):
    root = project(tmp_path)
    ingest_responses(root, [response()])
    item = candidates(root)[0]
    payload = automatic_record(root, item)

    def unavailable(_):
        raise RuntimeError("offline")

    assert queue_approval(root, item, payload, unavailable) is None
    assert candidates(root)[0]["review_state"] == "approved"
    sent = []
    resume_approvals(root, lambda p: sent.append(p) or 99)
    resume_approvals(root, lambda p: pytest.fail("must not submit twice"))
    assert sent == [payload]
    assert (
        json.loads((root / ".cache/puja/review_decisions.json").read_text())[item["candidate_id"]][
            "issue_number"
        ]
        == 99
    )


def test_approval_transport_recovers_existing_issue(tmp_path):
    from food_safety.puja.review_queue import issue_body

    root = project(tmp_path)
    payload = automatic_record(root, candidate())

    def api(method, endpoint, payload_unused=None):
        assert method == "GET"
        if endpoint == "user":
            return {"login": "shubha07m"}
        return [
            {
                "number": 99,
                "user": {"login": "shubha07m"},
                "title": "Puja approval " + payload["candidate_id"],
                "body": issue_body(payload),
            }
        ]

    assert submit_approval(payload, api=api) == 99


def test_unknown_city_is_retained_not_assigned_false_region(tmp_path):
    root = project(tmp_path)
    ingest_responses(root, [response(**{"City / region": "Somewhere unknown"})])
    assert len(read(root)["candidates"]) == 1
    assert candidates(root)[0]["region"] is None
    assert "APPROVE" in render(root, "token")


def test_desktop_oauth_readonly_loopback_and_private_token(tmp_path, monkeypatch):
    from types import SimpleNamespace

    folder = tmp_path / sheets.PRIVATE
    folder.mkdir(parents=True)
    (folder / "oauth-client.json").write_text(json.dumps({"installed": {"client_id": "fixture"}}))
    calls = []
    creds = SimpleNamespace(
        valid=True, scopes=sheets.SCOPES, client_id="fixture", to_json=lambda: '{"fixture":true}'
    )

    class Flow:
        @classmethod
        def from_client_config(cls, config, scopes, **kwargs):
            assert "installed" in config and scopes == sheets.SCOPES
            assert kwargs["autogenerate_code_verifier"]
            return cls()

        def run_local_server(self, **kwargs):
            calls.append(kwargs)
            assert kwargs["host"] == "127.0.0.1" and kwargs["port"] == 0
            assert kwargs["access_type"] == "offline"
            return creds

    loader = SimpleNamespace(from_authorized_user_file=lambda *_: creds)
    monkeypatch.setattr(sheets, "oauth_types", lambda: (loader, None, RuntimeError, Flow))
    assert sheets.credentials(tmp_path) is creds
    token = folder / "oauth-token.json"
    assert token.stat().st_mode & 0o777 == 0o600
    assert sheets.credentials(tmp_path) is creds
    assert len(calls) == 1  # Cached authorization, no new browser consent.


def test_sheets_request_is_bounded_readonly_and_no_contact_retention(tmp_path, monkeypatch):
    from types import SimpleNamespace

    import httpx

    root = project(tmp_path)
    folder = root / sheets.PRIVATE
    folder.mkdir(parents=True)
    (folder / "sheet.json").write_text(json.dumps({"spreadsheet_id": "fixture-sheet-id"}))
    row = response()

    def transport(request):
        assert request.method == "GET"
        assert request.url.host == "sheets.googleapis.com"
        assert "A1%3AZ10002" in str(request.url)
        assert request.headers["Authorization"] == "Bearer fixture-token"
        return httpx.Response(200, json={"values": [list(row), list(row.values())]})

    factory = httpx.Client
    monkeypatch.setattr(sheets, "credentials", lambda _: SimpleNamespace(token="fixture-token"))
    monkeypatch.setattr(
        sheets.httpx,
        "Client",
        lambda **kwargs: factory(transport=httpx.MockTransport(transport), **kwargs),
    )
    assert "1 new" in sheets.sync(root)
    assert "0 new" in sheets.sync(root)
    assert "must-not-retain" not in (root / STORE).read_text()


def test_sparse_sheet_approval_to_scheduled_static_publication(tmp_path):
    from food_safety.puja.approvals import publish_approved
    from food_safety.puja.pipeline import build_public
    from food_safety.puja.review_queue import issue_body

    root = project(tmp_path)
    sheets.sync(root, reader=lambda _: [response()])
    item = candidates(root)[0]
    value = automatic_record(root, item)
    issues = []

    def submit(payload):
        issues.append(
            {
                "number": 100,
                "title": "Puja approval " + payload["candidate_id"],
                "body": issue_body(payload),
                "user": {"login": "shubha07m"},
            }
        )
        return 100

    queue_approval(root, item, value, submit)
    assert publish_approved(root, api=lambda *_: issues)["approved_added"] == 1
    published = build_public(root)
    record = next(r for r in published["records"] if r["name"] == "River Puja")
    assert record["edition"] is None and record["latitude"] is None
    assert record["sources"][0]["evidence_kind"] == "owner_attestation"
    assert "Contact email" not in json.dumps(published)
