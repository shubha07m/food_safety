import runpy
import subprocess
from pathlib import Path

from food_safety.config import ROOT

audit = runpy.run_path(ROOT / "scripts/audit_repository.py")["audit"]


def test_current_tree_excludes_private_and_obsolete_artifacts():
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    assert "data/pending.json" not in tracked
    assert "data/rejected.json" not in tracked
    assert not any(path.startswith(("data/history/", "data/tmp/")) for path in tracked)
    assert not (ROOT / "Wb-Food-Safety-Tracker.html").exists()
    assert not any(
        "conversation" in path.casefold() or "scratch" in path.casefold()
        for path in tracked
    )


def test_public_readme_identity_and_rights_are_explicit():
    readme = (ROOT / "README.md").read_text()
    assert "Shubhabrata Mukherjee" in readme
    assert "https://github.com/shubha07m" in readme
    assert "Lawrence Berkeley National Laboratory" in readme
    assert "not affiliated with, sponsored by, endorsed by" in readme
    assert "Third-party content and trademarks" in readme
    assert "/Users/" not in readme


def test_no_tracked_environment_or_large_private_dump():
    tracked = subprocess.check_output(["git", "ls-files"], cwd=ROOT, text=True).splitlines()
    assert ".env" not in tracked
    for relative in tracked:
        path = ROOT / relative
        if path.is_file():
            assert path.stat().st_size < 2_000_000


def test_public_audit_does_not_ignore_server_side_pull_refs():
    result = audit()
    assert result["local_history_sanitized"] is True
    assert result["affected_pull_refs"] > 0
    assert result["github_pull_refs_cleared"] is False
    assert result["pull_ref_sensitive_content_found"] is False
    assert result["audit_passed"] is True
    assert result["ready_for_public_visibility"] is True


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def _audit_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.name", "Fixture Maintainer")
    _git(root, "config", "user.email", "fixture@users.noreply.github.com")
    (root / "config").mkdir()
    (root / "config/public_repository.yml").write_text(
        "github_pull_refs_cleared: false\naffected_pull_refs: 1\n"
        "retained_actions_artifacts: 0\n"
    )
    (root / "README.md").write_text("Public fixture repository.\n")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "initial public tree")
    return root


def test_controlled_branch_history_contamination_remains_blocking(tmp_path):
    root = _audit_fixture(tmp_path)
    (root / ".env").write_text("temporary fixture\n")
    _git(root, "add", ".env")
    _git(root, "commit", "-m", "contaminated controlled history")
    (root / ".env").unlink()
    _git(root, "add", "-u")
    _git(root, "commit", "-m", "remove from current tree")

    result = audit(root)
    assert result["current_private_paths"] == []
    assert result["historical_private_paths"] == [".env"]
    assert result["local_history_sanitized"] is False
    assert result["audit_passed"] is False


def test_ordinary_local_pull_ref_is_reported_but_not_blocking(tmp_path):
    root = _audit_fixture(tmp_path)
    _git(root, "update-ref", "refs/pull/1/head", "HEAD")

    result = audit(root)
    assert result["local_pull_refs_detected"] == ["refs/pull/1/head"]
    assert result["github_pull_refs_cleared"] is False
    assert result["pull_ref_sensitive_content_found"] is False
    assert result["local_history_sanitized"] is True
    assert result["audit_passed"] is True


def test_sensitive_content_in_pull_ref_is_reported_and_blocking(tmp_path):
    root = _audit_fixture(tmp_path)
    _git(root, "switch", "-c", "pull-fixture")
    (root / ".env").write_text('api_key="' + "A" * 32 + '"\n')
    _git(root, "add", ".env")
    _git(root, "commit", "-m", "sensitive pull fixture")
    pull_commit = _git(root, "rev-parse", "HEAD")
    _git(root, "switch", "main")
    _git(root, "branch", "-D", "pull-fixture")
    _git(root, "update-ref", "refs/pull/1/head", pull_commit)

    result = audit(root)
    assert result["local_history_sanitized"] is True
    assert result["pull_ref_private_paths"] == [".env"]
    assert result["pull_ref_secret_pattern_paths"] == [".env"]
    assert result["pull_ref_sensitive_content_found"] is True
    assert result["audit_passed"] is False
