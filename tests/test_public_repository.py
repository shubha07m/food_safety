import runpy
import subprocess

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
    assert result["affected_pull_refs"] == 7
    assert result["github_pull_refs_cleared"] is False
    assert result["ready_for_public_visibility"] is False
