"""Bounded current-tree and reachable-history audit; never prints matched values."""

import json
import re
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
MAX_BYTES = 64_000_000
SECRET = re.compile(
    rb"BEGIN [A-Z ]*PRIVATE KEY|github_pat_[A-Za-z0-9_]{30,}|"
    rb"gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}|AIza[A-Za-z0-9_-]{35}|"
    rb"(?:api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_./+-]{20,}",
    re.I,
)
PRIVATE_PREFIXES = ("data/history/", "data/tmp/", ".cache/", "logs/")
PRIVATE_PATHS = {"data/pending.json", "data/rejected.json", ".env"}
SUSPICIOUS_NAMES = re.compile(r"(?:conversation|chatgpt|codex|scratch|brainstorm)", re.I)
SCAN_SOURCE_EXEMPT = {
    "scripts/audit_repository.py",
    "scripts/verify_public_output.py",
    "tests/test_public_repository.py",
}
ALLOWED_AUTHOR_DOMAINS = {"users.noreply.github.com"}


def git(root, *args, data=None):
    return subprocess.check_output(["git", *args], cwd=root, input=data)


def refs(root, *prefixes):
    if not prefixes:
        return []
    return git(root, "for-each-ref", "--format=%(refname)", *prefixes).decode().splitlines()


def reachable_blobs(root, revisions):
    if not revisions:
        return [], 0
    paths = {}
    for line in git(root, "rev-list", "--objects", *revisions).splitlines():
        parts = line.decode(errors="replace").split(" ", 1)
        if len(parts) == 2 and parts[1] != "reports/public_repository_audit.json":
            paths[parts[0]] = parts[1]
    checks = git(root, "cat-file", "--batch-check", data=("\n".join(paths) + "\n").encode())
    blobs, total = [], 0
    for line in checks.decode().splitlines():
        sha, kind, size = line.split()
        if kind != "blob":
            continue
        total += int(size)
        if int(size) > 2_000_000 or total > MAX_BYTES:
            raise SystemExit("Audit cap reached; inspect oversized Git objects manually.")
        blobs.append(sha)
    payload = git(root, "cat-file", "--batch", data=("\n".join(blobs) + "\n").encode())
    cursor, result = 0, []
    for sha in blobs:
        end = payload.index(b"\n", cursor)
        size = int(payload[cursor:end].split()[-1])
        body = payload[end + 1 : end + 1 + size]
        cursor = end + 2 + size
        result.append((paths[sha], body))
    return result, total


def content_findings(blobs):
    private = sorted(
        {
            path
            for path, _ in blobs
            if path in PRIVATE_PATHS
            or path.startswith(PRIVATE_PREFIXES)
            or SUSPICIOUS_NAMES.search(path)
        }
    )
    secrets = sorted({path for path, body in blobs if SECRET.search(body)})
    machine = sorted(
        {
            path
            for path, body in blobs
            if path not in SCAN_SOURCE_EXEMPT
            and (b"/Users/" in body or b"/opt/homebrew/" in body)
        }
    )
    return private, secrets, machine


def audit(root=ROOT):
    tracked = [path for path in git(root, "ls-files", "-z").decode().split("\0") if path]
    current_bodies = {
        path: (root / path).read_bytes()
        for path in tracked
        if (root / path).is_file() and (root / path).stat().st_size <= 2_000_000
    }
    current_private = sorted(
        path
        for path in tracked
        if path in PRIVATE_PATHS
        or path.startswith(PRIVATE_PREFIXES)
        or SUSPICIOUS_NAMES.search(path)
    )
    controlled_refs = refs(root, "refs/heads", "refs/tags")
    pull_refs = refs(root, "refs/pull")
    blobs, byte_count = reachable_blobs(root, controlled_refs)
    pull_blobs, pull_byte_count = reachable_blobs(root, pull_refs)
    history_private, history_secrets, history_machine = content_findings(blobs)
    pull_private, pull_secrets, pull_machine = content_findings(pull_blobs)
    _, current_secrets, current_machine = content_findings(current_bodies.items())
    secret_paths = sorted(set(history_secrets) | set(current_secrets))
    machine_paths = sorted(set(history_machine) | set(current_machine))
    authors = (
        git(root, "log", *controlled_refs, "--format=%ae").decode().splitlines()
        if controlled_refs
        else []
    )
    public_author_emails = sorted(
        {email for email in authors if email.rsplit("@", 1)[-1] not in ALLOWED_AUTHOR_DOMAINS}
    )
    remote = yaml.safe_load((root / "config/public_repository.yml").read_text())
    result = {
        "scope": (
            "current tracked tree and controlled refs/heads plus refs/tags; "
            "GitHub-managed refs/pull scanned and reported separately when locally available"
        ),
        "controlled_refs_scanned": controlled_refs,
        "tracked_files": len(tracked),
        "history_blobs_scanned": len(blobs),
        "history_bytes_scanned": byte_count,
        "current_private_paths": current_private,
        "historical_private_paths": history_private,
        "secret_pattern_paths": secret_paths,
        "historical_machine_path_files": machine_paths,
        "public_author_email_metadata": public_author_emails,
        "github_pull_refs_cleared": bool(remote["github_pull_refs_cleared"]),
        "affected_pull_refs": int(remote["affected_pull_refs"]),
        "local_pull_refs_detected": pull_refs,
        "pull_ref_history_blobs_scanned": len(pull_blobs),
        "pull_ref_history_bytes_scanned": pull_byte_count,
        "pull_ref_private_paths": pull_private,
        "pull_ref_secret_pattern_paths": pull_secrets,
        "pull_ref_machine_path_files": pull_machine,
        "retained_actions_artifacts": int(remote["retained_actions_artifacts"]),
    }
    result["local_history_sanitized"] = not any(
        result[key]
        for key in [
            "current_private_paths",
            "historical_private_paths",
            "secret_pattern_paths",
            "historical_machine_path_files",
        ]
    )
    result["pull_ref_sensitive_content_found"] = any(
        result[key]
        for key in [
            "pull_ref_private_paths",
            "pull_ref_secret_pattern_paths",
            "pull_ref_machine_path_files",
        ]
    )
    # GitHub retains refs/pull as normal server-managed contribution metadata.
    # Their mere existence is informational. Actual sensitive content found in a
    # locally available pull ref remains a blocking security result.
    result["audit_passed"] = (
        result["local_history_sanitized"] and not result["pull_ref_sensitive_content_found"]
    )
    result["ready_for_public_visibility"] = result["audit_passed"]
    return result


def main():
    result = audit()
    (ROOT / "reports/public_repository_audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(
        json.dumps(
            {
                key: len(value) if isinstance(value, list) else value
                for key, value in result.items()
            }
        )
    )
    raise SystemExit(0 if result["audit_passed"] else 2)


if __name__ == "__main__":
    main()
