"""Bounded Git-object audit; report paths/counts, never matched secret values."""

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECRET = re.compile(
    rb"BEGIN [A-Z ]*PRIVATE KEY|github_pat_[A-Za-z0-9_]{30,}"
    rb"|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{30,}"
)


def git(*args, data=None):
    return subprocess.check_output(["git", *args], cwd=ROOT, input=data)


def main():
    objects = git("rev-list", "--objects", "--all").splitlines()
    paths = {}
    for line in objects:
        parts = line.decode().split(" ", 1)
        if len(parts) == 2:
            paths[parts[0]] = parts[1]
    checks = git("cat-file", "--batch-check", data=("\n".join(paths) + "\n").encode())
    selected = []
    total = 0
    for line in checks.decode().splitlines():
        sha, kind, size = line.split()
        if kind == "blob":
            if int(size) > 2_000_000 or total + int(size) > 32_000_000:
                raise SystemExit("Audit cap reached; inspect oversized Git objects manually.")
            total += int(size)
            selected.append(sha)
    payload = git("cat-file", "--batch", data=("\n".join(selected) + "\n").encode())
    cursor = 0
    secret_paths, machine_paths = set(), set()
    for sha in selected:
        end = payload.index(b"\n", cursor)
        size = int(payload[cursor:end].split()[-1])
        body = payload[end + 1 : end + 1 + size]
        cursor = end + 2 + size
        if SECRET.search(body):
            secret_paths.add(paths[sha])
        if b"/Users/" in body or b"/opt/homebrew/" in body:
            machine_paths.add(paths[sha])
    private_paths = sorted(
        {
            p
            for p in paths.values()
            if p.startswith("data/history/") or p in {"data/pending.json", "data/rejected.json"}
        }
    )
    report = {
        "scope": "all locally available Git refs; known token/key patterns only",
        "objects_scanned": len(selected),
        "bytes_scanned": total,
        "secret_pattern_paths": sorted(secret_paths),
        "historical_machine_path_files": sorted(machine_paths),
        "historical_private_artifact_paths": private_paths,
        "safe_to_make_public_without_history_review": False,
    }
    (ROOT / "reports/public_repository_audit.json").write_text(json.dumps(report, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: (len(value) if isinstance(value, list) else value)
                for key, value in report.items()
            }
        )
    )


if __name__ == "__main__":
    main()
