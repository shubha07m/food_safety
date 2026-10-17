"""Real Git/approval writer tests, with local bare remotes only; never GitHub mutations."""

import shutil
from pathlib import Path

import pytest
import yaml
from test_puja_approvals import candidate, git, git_project

from food_safety.puja import approval_release as release
from food_safety.puja.approvals import queue_approval
from food_safety.puja.pipeline import build_public, load_config
from food_safety.puja.review_queue import candidate_id, compile_record

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def repo(tmp_path):
    root = git_project(tmp_path)
    (root / "scripts").mkdir()
    shutil.copy(ROOT / "scripts/stage_generated.py", root / "scripts/stage_generated.py")
    (root / "data").mkdir()
    (root / "site/data").mkdir()
    (root / "data/status.json").write_text('{"refresh": 0}\n')
    build_public(root)
    git(root, "add", "scripts", "data", "site/data")
    git(root, "commit", "-m", "production fixture")
    git(root, "branch", "main")
    git(root, "push", "origin", "main", "develop")
    return root


def approve(root, name="River Durga Puja"):
    item = candidate()
    item["name"] = name
    item["fields"]["name"] = {"value": name, "evidence": {
        "passage_id": "P001", "original_quote": name,
    }}
    item["candidate_id"] = candidate_id(item["region"], item["source_url"], name)
    payload = compile_record(root, item, "source_listed")
    sha = queue_approval(root, item, payload)
    assert sha
    return sha


def refresh(root, n=1):
    git(root, "checkout", "main")
    for i in range(1, n + 1):
        (root / "data/status.json").write_text(f'{{"refresh": {i}}}\n')
        git(root, "add", "data/status.json")
        git(root, "commit", "-m", release.REFRESH)
    git(root, "push", "origin", "main")
    git(root, "checkout", "develop")
    return git(root, "rev-parse", "origin/main")


def prepare(root, sha):
    plan = release.plan(root, "origin/main", sha)
    git(root, "checkout", "--detach", plan["main"])
    return plan


def test_actual_writer_accepted_and_release_preserves_refreshes_and_is_idempotent(repo):
    sha = approve(repo)
    main = refresh(repo, 3)
    plan = prepare(repo, sha)
    assert plan["approvals"][0]["sha"] == sha
    assert plan["approvals"][0]["files"] == ["config/puja-london.yml"]
    merged = release.integrate(repo, plan, validator=build_public)
    assert release.ancestor(repo, main, merged) and release.ancestor(repo, sha, merged)
    assert (repo / "data/status.json").read_text() == '{"refresh": 3}\n'
    release.publish(repo, plan, merged)
    assert git(repo, "rev-parse", "origin/main") == merged
    assert git(repo, "rev-parse", "origin/develop") == merged
    assert release.plan(repo, merged, sha)["already_released"]
    again = release.plan(repo, merged, merged)
    result = release.integrate(repo, again, validator=lambda _: pytest.fail("duplicate build"))
    assert result == merged
    release.publish(repo, again, merged)
    assert sum(p.name == "River Durga Puja" for p in load_config(repo).published) == 1


@pytest.mark.parametrize("path", ["site/app.js", ".github/workflows/evil.yml",
                                 "site/data/pandals.json", "config/regions.yml"])
def test_approval_message_with_unexpected_path_rejected(repo, path):
    sha = approve(repo)
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(target.read_text() + "\n" if target.exists() else "unexpected\n")
    git(repo, "add", "--", path)
    git(repo, "commit", "--amend", "--no-edit")
    with pytest.raises(release.Blocked, match="unexpected changed path"):
        release.classify(repo, git(repo, "rev-parse", "HEAD"))
    assert not release.ancestor(repo, sha, "origin/main")


def test_ordinary_commit_and_mixed_history_rejected(repo):
    (repo / "README.md").write_text("Ordinary code flow\n")
    git(repo, "add", "README.md")
    git(repo, "commit", "-m", "Ordinary change")
    git(repo, "push", "origin", "develop")
    ordinary = git(repo, "rev-parse", "HEAD")
    with pytest.raises(release.Blocked, match="approval-convention"):
        release.classify(repo, ordinary)
    sha = approve(repo)
    with pytest.raises(release.Blocked, match="approval-convention"):
        release.plan(repo, "origin/main", sha)


@pytest.mark.parametrize("tamper", ["metadata", "second_record", "candidate", "revision"])
def test_message_and_catalog_paths_alone_are_insufficient(repo, tamper):
    sha = approve(repo)
    message = release.message(repo, sha)
    path = repo / "config/puja-london.yml"
    raw = yaml.safe_load(path.read_text())
    if tamper == "metadata":
        raw["unrelated"] = "not approval data"
    elif tamper == "second_record":
        raw["published"][0]["name"] += " changed"
    elif tamper == "candidate":
        message = message.replace(release.APPROVAL.fullmatch(message)[1], "pc-" + "b" * 20)
    else:
        message = message.replace(release.APPROVAL.fullmatch(message)[2], "b" * 64)
    path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False))
    git(repo, "add", "--", "config/puja-london.yml")
    git(repo, "commit", "--amend", "-m", message)
    with pytest.raises(ValueError):
        release.classify(repo, git(repo, "rev-parse", "HEAD"))


def test_main_non_refresh_or_unexpected_refresh_blocks(repo):
    sha = approve(repo)
    git(repo, "checkout", "main")
    (repo / "bad.py").write_text("pass\n")
    git(repo, "add", "bad.py")
    git(repo, "commit", "-m", "code on main")
    with pytest.raises(release.Blocked, match="non-refresh"):
        release.plan(repo, "main", sha)
    git(repo, "commit", "--amend", "-m", release.REFRESH)
    with pytest.raises(release.Blocked, match="unexpected changed path"):
        release.plan(repo, "main", sha)


def test_batch_releases_only_verified_approvals(repo):
    first = approve(repo)
    second = approve(repo, "Second Puja")
    refresh(repo)
    plan = prepare(repo, second)
    assert [a["sha"] for a in plan["approvals"]] == [first, second]
    merged = release.integrate(repo, plan, validator=build_public)
    release.publish(repo, plan, merged)
    assert release.ancestor(repo, first, merged)
    assert release.ancestor(repo, second, merged)


def test_conflict_and_validation_failure_cannot_change_remote(repo):
    sha = approve(repo)
    plan = prepare(repo, sha)
    before = git(repo, "ls-remote", "origin")

    def failing(_):
        raise release.Blocked("approval validation failed: fixture")

    with pytest.raises(release.Blocked, match="validation failed"):
        release.integrate(repo, plan, validator=failing)
    assert git(repo, "ls-remote", "origin") == before
    git(repo, "merge", "--abort")
    # Manufacture a conflict in this disposable fixture to exercise fail-closed Git handling.
    path = repo / "config/puja-london.yml"
    path.write_text(path.read_text() + "conflicting: true\n")
    git(repo, "add", "--", "config/puja-london.yml")
    git(repo, "commit", "-m", "conflict fixture")
    plan["main"] = git(repo, "rev-parse", "HEAD")
    with pytest.raises(release.Blocked, match="git merge failed"):
        release.integrate(repo, plan, validator=lambda _: pytest.fail("conflict passed"))
    assert git(repo, "ls-remote", "origin") == before


def test_unexpected_generated_output_blocks(repo):
    sha = approve(repo)
    plan = prepare(repo, sha)

    def unexpected(root):
        (root / "site/repository.json").write_text('{"bad":"not approval output"}\n')

    before = git(repo, "ls-remote", "origin")
    with pytest.raises(release.Blocked, match="unexpected generated path"):
        release.integrate(repo, plan, validator=unexpected)
    assert git(repo, "ls-remote", "origin") == before


def test_concurrent_approval_blocks_atomic_publication(repo):
    sha = approve(repo)
    plan = prepare(repo, sha)
    merged = release.integrate(repo, plan, validator=build_public)
    git(repo, "checkout", "develop")
    approve(repo, "Second Puja")
    with pytest.raises(release.Blocked, match="advanced during validation"):
        release.publish(repo, plan, merged)
    assert git(repo, "rev-parse", "origin/main") == plan["main"]


def test_remote_rejection_is_atomic_no_partial_branch_update(repo):
    sha = approve(repo)
    plan = prepare(repo, sha)
    merged = release.integrate(repo, plan, validator=build_public)
    # Simulate server protection on main. The push contains no force/bypass option.
    hook = repo / ".cache/remote.git/hooks/update"
    hook.write_text('#!/bin/sh\n[ "$1" != refs/heads/main ]\n')
    hook.chmod(0o755)
    with pytest.raises(release.Blocked, match="git push failed"):
        release.publish(repo, plan, merged)
    assert git(repo, "ls-remote", "origin", "refs/heads/main").startswith(plan["main"])
    assert git(repo, "ls-remote", "origin", "refs/heads/develop").startswith(sha)


def test_next_approval_automatically_fast_forwards_owner_and_keeps_dirty_files(repo):
    sha = approve(repo)
    refresh(repo, 2)
    plan = prepare(repo, sha)
    merged = release.integrate(repo, plan, validator=build_public)
    release.publish(repo, plan, merged)
    git(repo, "checkout", "develop")
    assert git(repo, "rev-parse", "HEAD") == sha
    (repo / "site/repository.json").write_text('{"unrelated":"preserve"}\n')
    new_sha = approve(repo, "Second Puja")
    assert release.parents(repo, new_sha) == [merged]
    assert (repo / "site/repository.json").read_text() == '{"unrelated":"preserve"}\n'
    assert git(repo, "diff", "--cached", "--name-only") == ""
    assert release.plan(repo, "origin/main", new_sha)["approvals"][0]["sha"] == new_sha


def test_failed_ci_blocks_before_integration_and_writes_summary(repo, monkeypatch):
    sha = approve(repo)
    before = git(repo, "ls-remote", "origin")
    summary = repo / ".cache/summary.md"
    monkeypatch.chdir(repo)
    monkeypatch.setenv("APPROVAL_CI_RESULT", "failure")
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    monkeypatch.setattr("sys.argv", ["approval_release", "--sha", sha, "--publish"])
    with pytest.raises(SystemExit):
        release.main()
    assert "APPROVAL RELEASE BLOCKED" in summary.read_text()
    assert "approval CI did not succeed" in summary.read_text()
    assert git(repo, "ls-remote", "origin") == before


def test_workflow_uses_trusted_main_and_same_refresh_lock():
    wf = yaml.load((ROOT / ".github/workflows/puja-approval-release.yml").read_text(),
                   Loader=yaml.BaseLoader)
    assert set(wf["on"]) == {"workflow_run"}
    assert wf["on"]["workflow_run"]["workflows"] == ["CI"]
    assert wf["on"]["workflow_run"]["branches"] == ["develop"]
    assert wf["concurrency"] == {"group": "source-update", "cancel-in-progress": "false"}
    job = wf["jobs"]["release"]
    assert job["permissions"] == {"contents": "write"}
    assert job["steps"][0]["with"]["ref"] == "main"
    assert job["steps"][0]["with"]["persist-credentials"] == "false"
    assert "--force" not in str(wf)
    assert "GEMINI_API_KEY" not in str(wf)
    assert "--publish" in str(wf)


def test_validation_gate_fresh_checkout_order_and_no_provider_secrets(tmp_path, monkeypatch):
    from types import SimpleNamespace

    (tmp_path / "tests").mkdir()
    calls = []

    def run(args, **kwargs):
        assert (tmp_path / ".cache").is_dir()
        assert not {"GH_TOKEN", "GEMINI_API_KEY", "GOOGLE_MAPS_API_KEY"} & kwargs["env"].keys()
        assert kwargs["env"]["AUTO_PUBLISH"] == kwargs["env"]["LLM_ENABLED"] == "false"
        calls.append(args)
        return SimpleNamespace(returncode=0)

    monkeypatch.setenv("GH_TOKEN", "fixture-never-forward")
    monkeypatch.setenv("GEMINI_API_KEY", "fixture-never-forward")
    monkeypatch.setattr(release.subprocess, "run", run)
    release.validate_release(tmp_path)
    assert sum(args[-1] == "build" for args in calls) == 2
    assert next(i for i, c in enumerate(calls) if "build" in c) < next(
        i for i, c in enumerate(calls) if "pytest" in c
    )
    assert any("scripts/verify_public_output.py" in c for c in calls)
    assert any("scripts/stage_generated.py" in c for c in calls)
    assert not any(word in c for c in calls for word in ("discover", "extract", "refresh"))
