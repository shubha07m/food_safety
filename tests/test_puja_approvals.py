import http.client
import json
import shutil
import subprocess
import threading
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pytest

from food_safety.puja.approvals import (
    canonical_changes,
    deliver_approval,
    queue_approval,
    represented,
    restore_approvals,
    resume_approvals,
)
from food_safety.puja.intake import import_form_csv, submission_seeds
from food_safety.puja.pipeline import build_public, load_config
from food_safety.puja.review_queue import (
    candidate_id,
    candidates,
    compile_record,
    save_decision,
    validate_approval,
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
    assert validate_approval(reviewed) == reviewed
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
    assert validate_approval(payload) == payload
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
    assert validate_approval(value) == value


def git(root, *args):
    return subprocess.check_output(
        ["git", *args], cwd=root, text=True, stderr=subprocess.PIPE
    ).strip()


def git_project(tmp_path):
    root = project(tmp_path)
    git(root, "init", "--initial-branch=develop")
    git(root, "config", "user.name", "Fixture owner")
    git(root, "config", "user.email", "owner@example.org")
    (root / ".gitignore").write_text(".cache/\n.env\n")
    (root / "site").mkdir()
    (root / "site/repository.json").write_text('{"fixture": true}\n')
    git(root, "add", "--", "config", ".gitignore", "site/repository.json")
    git(root, "commit", "-m", "fixture")
    remote = tmp_path / ".cache/remote.git"
    remote.parent.mkdir()
    git(root, "init", "--bare", str(remote))
    git(root, "remote", "add", "origin", str(remote))
    git(root, "push", "-u", "origin", "develop")
    return root


def test_approve_commits_only_catalog_and_preserves_private_dirty_files(tmp_path):
    root = git_project(tmp_path)
    item = candidate()
    payload = compile_record(
        root, item, "current_edition_reviewed", at=datetime(2026, 9, 24, tzinfo=UTC)
    )
    count = len(load_config(root).published)
    dirty = root / "site/repository.json"
    dirty.write_text('{"unrelated": "keep exactly"}\n')
    private = root / ".cache/puja"
    private.mkdir()
    for name in ("oauth-client.json", "oauth-token.json", "queue.json", "sheet.json"):
        (private / name).write_text('{"private":"must never publish"}')
    (root / ".env").write_text("PRIVATE_FIXTURE=private")
    commit = queue_approval(root, item, payload)
    assert commit == git(root, "rev-parse", "refs/remotes/origin/develop")
    assert git(root, "show", "--format=", "--name-only", commit) == "config/puja-london.yml"
    assert git(root, "diff", "--cached", "--name-only") == ""
    assert dirty.read_text() == '{"unrelated": "keep exactly"}\n'
    assert ".cache" not in git(root, "ls-tree", "-r", "--name-only", "HEAD")
    assert ".env" not in git(root, "ls-tree", "-r", "--name-only", "HEAD")
    assert represented(root, payload)
    assert canonical_changes(root, payload) == {}
    assert queue_approval(root, item, payload) == commit
    resume_approvals(root)
    assert git(root, "rev-parse", "HEAD") == commit
    assert build_public(root)["record_count"] == count + 1
    result = next(
        p for p in load_config(root).published if p.pandal_id == payload["record"]["pandal_id"]
    )
    assert result.edition.confirmed and len(result.edition.programme_notes) == 1
    assert git(root, "ls-remote", "--heads", "origin").endswith("refs/heads/develop")
    assert len(git(root, "ls-remote", "--heads", "origin").splitlines()) == 1
    assert not (root / "config/puja-approved.json").exists()
    assert not (root / "config/puja-requests").exists()


def test_push_failure_retries_existing_commit_without_duplicates(tmp_path, monkeypatch, capsys):
    from food_safety.puja import approvals

    root = git_project(tmp_path)
    item = candidate()
    payload = compile_record(root, item, "source_listed")
    original = approvals._git

    def offline(root, *args):
        if args[0] == "push":
            raise RuntimeError("git_push_failed")
        return original(root, *args)

    monkeypatch.setattr(approvals, "_git", offline)
    assert queue_approval(root, item, payload) is None
    commit = git(root, "rev-parse", "HEAD")
    resume_approvals(root)
    assert git(root, "rev-parse", "HEAD") == commit
    assert capsys.readouterr().out.count("git_push_failed") == 1
    monkeypatch.setattr(approvals, "_git", original)
    resume_approvals(root)
    assert git(root, "rev-parse", "origin/develop") == commit
    resume_approvals(root)
    assert git(root, "rev-parse", "HEAD") == commit
    assert (
        sum(p.pandal_id == payload["record"]["pandal_id"] for p in load_config(root).published) == 1
    )


def test_reject_and_malformed_outbox_do_not_block_other_approvals(tmp_path, capsys):
    root = git_project(tmp_path)
    rejected = candidate()
    save_decision(root, rejected, "reject")
    payload = compile_record(root, rejected, "source_listed")
    with pytest.raises(ValueError, match="rejected_decision_preserved"):
        queue_approval(root, rejected, payload)
    assert not represented(root, payload)
    folder = root / ".cache/puja/approval_outbox"
    folder.mkdir()
    (folder / (rejected["candidate_id"] + ".json")).write_text(
        json.dumps({"candidate": rejected, "payload": payload})
    )
    (folder / ("pc-" + "f" * 20 + ".json")).write_text("invalid")
    good = candidate()
    good["name"] = "Other River Puja"
    good["fields"]["name"] = fact(good["name"], "Other River Puja in London")
    good["candidate_id"] = candidate_id("london", good["source_url"], good["name"])
    good_payload = compile_record(root, good, "source_listed")
    (folder / (good["candidate_id"] + ".json")).write_text(
        json.dumps({"candidate": good, "payload": good_payload})
    )
    resume_approvals(root)
    resume_approvals(root)
    assert capsys.readouterr().out.count("JSONDecodeError") == 1
    assert represented(root, good_payload)
    assert not represented(root, payload)
    decisions = json.loads((root / ".cache/puja/review_decisions.json").read_text())
    assert decisions[rejected["candidate_id"]]["decision"] == "reject"


@pytest.mark.parametrize("unsafe_state", ["staged", "catalog_dirty", "main", "unpublished_code"])
def test_unsafe_git_state_is_preserved_for_retry(tmp_path, unsafe_state):
    root = git_project(tmp_path)
    item = candidate()
    payload = compile_record(root, item, "source_listed")
    target = root / "config/puja-london.yml"
    if unsafe_state == "staged":
        (root / "site/repository.json").write_text("unrelated")
        git(root, "add", "site/repository.json")
    elif unsafe_state == "catalog_dirty":
        target.write_text(target.read_text() + "\n# unrelated\n")
    elif unsafe_state == "main":
        git(root, "checkout", "-b", "main")
    else:
        (root / "site/repository.json").write_text("unpublished code")
        git(root, "commit", "--only", "-m", "unrelated", "--", "site/repository.json")
    before = target.read_bytes()
    index = git(root, "diff", "--cached")
    head = git(root, "rev-parse", "HEAD")
    assert queue_approval(root, item, payload) is None
    assert target.read_bytes() == before
    assert git(root, "diff", "--cached") == index
    assert git(root, "rev-parse", "HEAD") == head
    assert (
        json.loads((root / ".cache/puja/review_decisions.json").read_text())[item["candidate_id"]][
            "decision"
        ]
        == "approved"
    )


def test_legacy_delivery_receipts_do_not_skip_canonical_persistence(tmp_path):
    root = git_project(tmp_path)
    item = candidate()
    payload = compile_record(root, item, "source_listed")
    folder = root / ".cache/puja/approval_outbox"
    folder.mkdir(parents=True)
    path = folder / (item["candidate_id"] + ".json")
    path.write_text(
        json.dumps(
            {
                "candidate": item,
                "payload": payload,
                "issue_number": 24,
                "request_path": "legacy-path",
            }
        )
    )
    save_decision(root, item, "approved", issue_number=24)
    before = (root / ".cache/puja/review_decisions.json").read_bytes()
    resume_approvals(root)
    assert represented(root, payload)
    assert json.loads(path.read_text())["canonical_commit"]
    assert (root / ".cache/puja/review_decisions.json").read_bytes() == before
    resume_approvals(root)


def test_fresh_laptop_restores_approval_from_canonical_evidence(tmp_path):
    root = git_project(tmp_path)
    item = candidate()
    payload = compile_record(root, item, "source_listed")
    deliver_approval(root, payload)
    assert not (root / ".cache/puja/review_decisions.json").exists()
    restore_approvals(root)
    decisions = json.loads((root / ".cache/puja/review_decisions.json").read_text())
    assert decisions[item["candidate_id"]]["decision"] == "approved"
    assert decisions[item["candidate_id"]]["source_revision"] == item["source_revision"]


def test_invalid_payload_cannot_modify_canonical_data(tmp_path):
    root = git_project(tmp_path)
    payload = compile_record(root, candidate(), "source_listed")
    original = (root / "config/puja-london.yml").read_bytes()
    payload["private_queue"] = "private"
    with pytest.raises(ValueError, match="approval_fields_invalid"):
        deliver_approval(root, payload)
    assert (root / "config/puja-london.yml").read_bytes() == original


def test_interrupted_catalog_write_is_recovered_on_restart(tmp_path, monkeypatch):
    from food_safety.puja import approvals

    root = git_project(tmp_path)
    item = candidate()
    payload = compile_record(root, item, "source_listed")
    original = approvals._git

    def interrupted(root, *args):
        if args[0] == "commit":
            raise KeyboardInterrupt
        return original(root, *args)

    monkeypatch.setattr(approvals, "_git", interrupted)
    with pytest.raises(KeyboardInterrupt):
        queue_approval(root, item, payload)
    assert (root / approvals.EDIT).exists()
    monkeypatch.setattr(approvals, "_git", original)
    resume_approvals(root)
    assert represented(root, payload)
    assert not (root / approvals.EDIT).exists()
    assert git(root, "rev-parse", "HEAD") == git(root, "rev-parse", "origin/develop")


@pytest.mark.parametrize(
    "identity,record_id",
    [
        ("pc-10be5643cfd1691b57d0", "ca-agomoni"),
        ("pc-18199c10fccc8e0ebb9f", "california-aantorik"),
        ("pc-1897600f525e7ea136c4", "gta-apcat"),
        ("pc-231aa72c405daf06467b", "california-aikotaan"),
        ("pc-59051a3a69ddebdf1e0f", "california-sanatan"),
        ("pc-683dd31210b05d14cde1", "california-utsav"),
        ("pc-871cd7aee60e2e285306", "ca-ankur"),
        ("pc-bdefa95041006bfcc5aa", "ca-pashchimi"),
    ],
)
def test_reconciled_approvals_are_in_normal_catalog(identity, record_id):
    config = load_config(ROOT)
    matches = [p for p in config.published if p.pandal_id == record_id]
    assert len(matches) == 1
    record = matches[0]
    assert any(
        s.source_revision_id
        and candidate_id(record.region_id, str(s.source_url), record.name) == identity
        for s in record.sources
    )
    if record_id == "gta-apcat":
        assert record.edition.confirmed and record.edition.year == 2026
        assert record.edition.location.latitude is not None


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
