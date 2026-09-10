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


def git(*args, data=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, input=data)


def reachable_blobs():
    paths = {}
    for line in git("rev-list", "--objects", "--all").splitlines():
        parts = line.decode(errors="replace").split(" ", 1)
        if len(parts) == 2 and parts[1] != "reports/public_repository_audit.json":
            paths[parts[0]] = parts[1]
    checks = git("cat-file", "--batch-check", data=("\n".join(paths) + "\n").encode())
    blobs, total = [], 0
    for line in checks.decode().splitlines():
        sha, kind, size = line.split()
        if kind != "blob":
            continue
        total += int(size)
        if int(size) > 2_000_000 or total > MAX_BYTES:
            raise SystemExit("Audit cap reached; inspect oversized Git objects manually.")
        blobs.append(sha)
    payload = git("cat-file", "--batch", data=("\n".join(blobs) + "\n").encode())
    cursor, result = 0, []
    for sha in blobs:
        end = payload.index(b"\n", cursor)
        size = int(payload[cursor:end].split()[-1])
        body = payload[end + 1 : end + 1 + size]
        cursor = end + 2 + size
        result.append((paths[sha], body))
    return result, total


def audit():
    tracked = [path for path in git("ls-files", "-z").decode().split("\0") if path]
    current_bodies = {
        path: (ROOT / path).read_bytes()
        for path in tracked
        if (ROOT / path).is_file() and (ROOT / path).stat().st_size <= 2_000_000
    }
    current_private = sorted(
        path
        for path in tracked
        if path in PRIVATE_PATHS
        or path.startswith(PRIVATE_PREFIXES)
        or SUSPICIOUS_NAMES.search(path)
    )
    blobs, byte_count = reachable_blobs()
    history_private = sorted(
        {
            path
            for path, _ in blobs
            if path in PRIVATE_PATHS
            or path.startswith(PRIVATE_PREFIXES)
            or SUSPICIOUS_NAMES.search(path)
        }
    )
    secret_paths = sorted(
        {path for path, body in blobs if SECRET.search(body)}
        | {path for path, body in current_bodies.items() if SECRET.search(body)}
    )
    machine_paths = sorted(
        {
            path
            for path, body in blobs
            if path not in SCAN_SOURCE_EXEMPT
            and (b"/Users/" in body or b"/opt/homebrew/" in body)
        }
        | {
            path
            for path, body in current_bodies.items()
            if path not in SCAN_SOURCE_EXEMPT
            and (b"/Users/" in body or b"/opt/homebrew/" in body)
        }
    )
    authors = git("log", "--all", "--format=%ae").decode().splitlines()
    public_author_emails = sorted(
        {email for email in authors if email.rsplit("@", 1)[-1] not in ALLOWED_AUTHOR_DOMAINS}
    )
    remote = yaml.safe_load((ROOT / "config/public_repository.yml").read_text())
    result = {
        "scope": (
            "current tracked tree contents and all locally reachable refs; "
            "bounded pattern scan"
        ),
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
        "retained_actions_artifacts": int(remote["retained_actions_artifacts"]),
    }
    result["local_history_sanitized"] = not any(
        result[key]
        for key in [
            "current_private_paths",
            "historical_private_paths",
            "secret_pattern_paths",
            "historical_machine_path_files",
            "public_author_email_metadata",
        ]
    )
    result["ready_for_public_visibility"] = (
        result["local_history_sanitized"] and result["github_pull_refs_cleared"]
    )
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
    raise SystemExit(0 if result["ready_for_public_visibility"] else 2)


if __name__ == "__main__":
    main()
