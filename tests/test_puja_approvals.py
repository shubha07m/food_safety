import base64
import http.client
import json
import shutil
import threading
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest

from food_safety.puja.approvals import (
    GithubAPIError,
    close_published,
    deliver_approval,
    migrate_outbox,
    publish_approved,
    request_path,
    resume_approvals,
)
from food_safety.puja.intake import import_form_csv, submission_seeds
from food_safety.puja.pipeline import build_public, load_config
from food_safety.puja.review_queue import (
    candidate_id,
    candidates,
    compile_record,
    issue_body,
    parse_issue_body,
    save_decision,
)
from food_safety.puja.review_server import handler, render

ROOT = Path(__file__).resolve().parents[1]


class GitQueueAPI:
    """Only the read/write Git calls needed by the public-safe request queue."""

    def __init__(self):
        self.branch = False
        self.files = {}
        self.writes = 0
        self.issues = []

    def __call__(self, method, endpoint, payload=None):
        if endpoint == "user":
            return {"login": "shubha07m"}
        if "issues?" in endpoint:
            return self.issues
        if endpoint.endswith("/git/ref/heads/main"):
            return {"object": {"sha": "a" * 40}}
        if endpoint.endswith("/git/ref/heads/puja-approvals"):
            if not self.branch:
                raise GithubAPIError(404)
            return {"object": {"sha": "b" * 40}}
        if endpoint.endswith("/git/refs") and method == "POST":
            self.branch = True
            return {}
        if "/contents/config/puja-requests" in endpoint:
            path = endpoint.split("/contents/", 1)[1].split("?", 1)[0]
            if method == "PUT":
                assert payload["branch"] == "puja-approvals"
                self.files[path] = base64.b64decode(payload["content"]).decode()
                self.writes += 1
                return {"content": {"path": path}}
            if path == "config/puja-requests":
                return [{"type": "file", "path": p} for p in self.files]
            if path not in self.files:
                raise GithubAPIError(404)
            return {
                "encoding": "base64",
                "content": base64.b64encode(self.files[path].encode()).decode(),
            }
        raise AssertionError((method, endpoint))


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


def test_existing_source_approval_adds_reviewed_revision_without_replacing_old_evidence(tmp_path):
    root = project(tmp_path)
    base = next(p for p in load_config(root).published if p.pandal_id == "ca-agomoni")
    item = candidate()
    item.update(
        name=base.name,
        region="california",
        source_url=str(base.sources[0].source_url),
        candidate_id=candidate_id("california", str(base.sources[0].source_url), base.name),
        duplicate_ids=[base.pandal_id],
        same_source_listing_ids=[base.pandal_id],
    )
    item["fields"] = {
        "name": fact(base.name, f"{base.name} organizer page"),
        "locality": {"value": base.city},
    }
    value = compile_record(root, item, "source_listed")
    assert len(value["record"]["sources"]) == len(base.sources) + 1
    assert value["record"]["sources"][-1]["source_revision_id"] == item["source_revision"]
    assert parse_issue_body(issue_body(value)) == value


def test_legacy_saved_approval_migration_and_once_only_warning(tmp_path, capsys):
    root = project(tmp_path)
    config = load_config(root)
    base = next(p for p in config.published if p.pandal_id == "ca-agomoni")
    source = next(s for s in config.sources if str(s.url) == str(base.sources[0].source_url))
    candidate_key = "pc-" + "a" * 20
    original = {
        "candidate": {"candidate_id": candidate_key, "source_revision": "b" * 64},
        "payload": {
            "candidate_id": candidate_key,
            "source_revision": "b" * 64,
            "monitor_revision": source.reviewed_revision,
            "tier": "source_listed",
            "record": {**base.model_dump(mode="json"), "last_verified_at": "2026-09-26T00:00:00Z"},
            "source": source.model_dump(mode="json"),
        },
    }
    save_decision(root, original["candidate"], "approved")
    folder = root / ".cache/puja/approval_outbox"
    folder.mkdir(parents=True)
    path = folder / f"{candidate_key}.json"
    path.write_text(json.dumps(original))
    bad = folder / ("pc-" + "c" * 20 + ".json")
    bad.write_text("invalid")
    report = migrate_outbox(root)
    assert report["repaired"] == [candidate_key]
    assert report["invalid"] and report["invalid"][0][0] == bad.stem
    assert json.loads((root / ".cache/puja/approval_backups" / path.name).read_text()) == original
    repaired = json.loads(path.read_text())["payload"]
    assert parse_issue_body(issue_body(repaired)) == repaired
    assert repaired["record"]["sources"][-1]["evidence_kind"] == "owner_attestation"
    assert migrate_outbox(root)["repaired"] == []
    sent = []
    resume_approvals(root, lambda p: sent.append(p) or request_path(p["candidate_id"]))
    resume_approvals(root, lambda _: pytest.fail("duplicate delivery"))
    assert len(sent) == 1
    assert capsys.readouterr().out.count("needs review") == 1
    assert (
        json.loads((root / ".cache/puja/review_decisions.json").read_text())[candidate_key][
            "decision"
        ]
        == "approved"
    )


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
        if "/contents/" in endpoint:
            raise GithubAPIError(404)
        if method == "GET":
            return [bad, issue, untrusted]
        closed.append((endpoint, payload))
        return {}

    first = publish_approved(root, api=api)
    assert first["approved_added"] == 1 and first["invalid"][0]["issue"] == 41
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


def test_git_approval_transport_requires_owner_and_is_idempotent(tmp_path):
    value = compile_record(project(tmp_path), candidate(), "source_listed")
    api = GitQueueAPI()
    path = request_path(value["candidate_id"])
    assert deliver_approval(value, api=api) == path
    assert deliver_approval(value, api=api) == path
    assert api.writes == 1
    assert json.loads(api.files[path]) == value
    assert "Contact email" not in api.files[path]
    assert "oauth" not in api.files[path]
    changed = {**value, "source_revision": "c" * 64}
    with pytest.raises(ValueError, match="approval_evidence_missing"):
        deliver_approval(changed, api=api)
    with pytest.raises(ValueError, match="github_owner_login_required"):
        deliver_approval(value, api=lambda *_: {"login": "other"})


def test_git_queue_publication_skips_malformed_and_avoids_legacy_duplicate(tmp_path):
    root = project(tmp_path)
    value = compile_record(root, candidate(), "source_listed")
    api = GitQueueAPI()
    path = deliver_approval(value, api=api)
    malformed = request_path("pc-" + "f" * 20)
    api.files[malformed] = '{"raw_candidate": "must never publish"}'
    api.issues = [
        {
            "number": 40,
            "title": "Puja approval " + value["candidate_id"],
            "body": issue_body(value),
            "user": {"login": "shubha07m"},
        }
    ]
    result = publish_approved(root, api=api)
    assert result["approved_added"] == 1
    assert result["already_published"] == 1
    assert result["invalid"][0]["request"] == malformed
    assert len(json.loads((root / "config/puja-approved.json").read_text())["approvals"]) == 1
    assert publish_approved(root, api=api)["approved_added"] == 0
    assert json.loads(api.files[path]) == value


def test_form_csv_import_keeps_contact_and_notes_out(tmp_path):
    root = project(tmp_path)
    private = root / ".cache/puja"
    private.mkdir(parents=True)
    path = private / "responses.csv"
    path.write_text(
        "Puja / organizer name,Region,City / region,Official organizer / event URL,"
        "Contact email,Short note\n"
        "River Puja,London region,London,https://example.org/event,"
        "private@example.org,private note\n"
    )
    assert import_form_csv(root, path)["imported"] == 1
    rows = submission_seeds(root)
    assert rows == [
        {
            "region": "london",
            "url": "https://example.org/event",
            "candidate_name": "River Puja",
            "origin": "google_form",
        }
    ]
    assert "private@example.org" not in json.dumps(rows)
    assert "private note" not in json.dumps(rows)
    assert import_form_csv(root, path)["imported"] == 0
    tracked = root / "responses.csv"
    tracked.write_text(path.read_text())
    with pytest.raises(ValueError, match="outside_tracked_tree"):
        import_form_csv(root, tracked)


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
                "action": "reject",
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
        assert candidates(root)[0]["review_state"] == "reject"
        # A changed source revision does not resurrect rejected candidates.
        raw = json.loads((campaign / "review.json").read_text())
        raw["sources"][0]["candidates"][0]["source_revision"] = "c" * 64
        (campaign / "review.json").write_text(json.dumps(raw))
        assert candidates(root)[0]["review_state"] == "reject"
        # Simulate a separate pending decision for the approval HTTP path.
        (root / ".cache/puja/review_decisions.json").write_text("{}")
        form = urlencode(
            {
                "token": "token",
                "candidate_id": candidates(root)[0]["candidate_id"],
                "revision": "c" * 64,
                "action": "approve",
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
