"""Fail-closed, production-trusted release of canonical approval commits only.

No provider calls, force pushes, temporary remote branches, or private outbox reads.
Run in a disposable detached checkout of current main, never an operator worktree.
"""

import argparse
import ast
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .approvals import canonical_changes, catalog_paths
from .pipeline import load_config
from .regions import load_regions
from .review_queue import candidate_id, validate_approval

APPROVAL = re.compile(
    r"data: approve Puja (pc-[a-f0-9]{20})\n\nPuja-Revision: ([a-f0-9]{64})"
)
RELEASE = re.compile(r"data: release Puja approvals\n\nPuja-Approvals: ([a-f0-9,]{40,})")
REFRESH = "data: validated refresh [automated-refresh]"


class Blocked(ValueError):
    pass


def git(root, *args):
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, timeout=120,
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
    )
    if result.returncode:
        # Do not echo remote URLs, credentials, payloads or arbitrary Git diagnostics.
        raise Blocked(f"git {args[0]} failed (conflict, concurrent update or protection)")
    return result.stdout.strip()


def ancestor(root, older, newer):
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer], cwd=root,
        capture_output=True, timeout=30,
    )
    if result.returncode not in (0, 1):
        raise Blocked("ancestry unavailable")
    return result.returncode == 0


def parents(root, sha):
    return git(root, "show", "-s", "--format=%P", sha).split()


def message(root, sha):
    return git(root, "show", "-s", "--format=%B", sha)


def changed(root, before, after, allowed):
    names = git(root, "diff", "--name-only", "--no-renames", before, after).splitlines()
    if not names:
        raise Blocked("empty approval/refresh diff")
    for path in names:
        if path not in allowed:
            raise Blocked(f"unexpected changed path: {path}")
        for revision in (before, after):
            entry = git(root, "ls-tree", revision, "--", path)
            if not entry.startswith("100644 blob "):
                raise Blocked(f"added/deleted/non-regular tracked path: {path}")
    return names


def catalog_snapshot(root, revision, target):
    paths = catalog_paths(root) | {"config/regions.yml"}
    for path in paths:
        dest = target / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(git(root, "show", f"{revision}:{path}") + "\n")


def classify(root, sha):
    """Reconstruct the public payload and reproduce canonical_changes exactly.

    A message is not an attestation. This proves the existing public commit contract,
    not the physical UI click; repository write access remains a trust boundary.
    """
    match = APPROVAL.fullmatch(message(root, sha))
    previous = parents(root, sha)
    if not match or len(previous) != 1:
        raise Blocked("not a single-parent approval-convention commit")
    identity, revision = match.groups()
    paths = changed(root, previous[0], sha, catalog_paths(root))
    with tempfile.TemporaryDirectory(prefix="puja-release-classify-") as directory:
        before, after = Path(directory) / "before", Path(directory) / "after"
        catalog_snapshot(root, previous[0], before)
        catalog_snapshot(root, sha, after)
        old, new = load_config(before), load_config(after)
        old_records = {p.pandal_id: p for p in old.published}
        new_records = {p.pandal_id: p for p in new.published}
        if old_records.keys() - new_records.keys():
            raise Blocked("approval removes a published record")
        updates = [p for k, p in new_records.items() if old_records.get(k) != p]
        if len(updates) != 1:
            raise Blocked("approval must change exactly one published record")
        record = updates[0]
        sources = [s for s in new.sources if s.region_id == record.region_id and any(
            str(e.source_url) == str(s.url) and e.source_revision_id == revision
            for e in record.sources
        ) and any(candidate_id(record.region_id, str(s.url), name) == identity
                  for name in [record.name, *record.aliases])]
        if len(sources) != 1:
            raise Blocked("candidate identity/source/revision is not unambiguous")
        source = sources[0]
        payload = {
            "candidate_id": identity, "source_revision": revision,
            "monitor_revision": source.reviewed_revision, "tier": "source_listed",
            "record": record.model_dump(mode="json"),
            "source": source.model_dump(mode="json"),
        }
        validate_approval(payload)
        expected = canonical_changes(before, payload)
        expected = {p: text for p, text in expected.items()
                    if text.strip() != git(root, "show", f"{previous[0]}:{p}")}
        if set(expected) != set(paths) or any(
            text.strip() != git(root, "show", f"{sha}:{p}") for p, text in expected.items()
        ):
            raise Blocked("diff is not exactly the canonical approval writer output")
    return {"sha": sha, "candidate": identity, "pandal": record.pandal_id,
            "region": record.region_id, "files": paths}


def refresh_paths(root):
    # Read the existing trusted generated allowlist, without copying a second list.
    tree = ast.parse((root / "scripts/stage_generated.py").read_text())
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "GENERATED" for t in node.targets
        ):
            return set(ast.literal_eval(node.value))
    raise Blocked("trusted generated allowlist unavailable")


def plan(root, main, develop):
    main, develop = (git(root, "rev-parse", f"{ref}^{{commit}}") for ref in (main, develop))
    if ancestor(root, develop, main):
        return {"main": main, "develop": develop, "approvals": [], "already_released": True}
    bases = git(root, "merge-base", "--all", main, develop).splitlines()
    if len(bases) != 1:
        raise Blocked("ambiguous production ancestry")
    base = bases[0]
    commits = git(root, "rev-list", "--reverse", f"{main}..{develop}").splitlines()
    if not 1 <= len(commits) <= 20:
        raise Blocked("approval batch must contain 1–20 commits")
    approvals = []
    prior = base
    for sha in commits:
        if parents(root, sha) != [prior]:
            raise Blocked("develop history is not a linear approval-only chain")
        approvals.append(classify(root, sha))
        prior = sha
    # Production may have advanced by normal data refreshes, never unrelated code.
    allowed = refresh_paths(root)
    for sha in git(root, "rev-list", f"{base}..{main}").splitlines():
        previous = parents(root, sha)
        if len(previous) != 1 or message(root, sha) != REFRESH:
            raise Blocked("main diverged by a non-refresh commit; manual release required")
        changed(root, previous[0], sha, allowed)
    return {"main": main, "develop": develop, "base": base, "approvals": approvals,
            "already_released": False}


def derived_paths(root):
    allowed = {"data/pandals.json", "site/data/pandals.json"}
    for region in load_regions(root).regions:
        # Only re-association of committed snapshots, never acquisition or config edits.
        for path in (region.food_data, region.provider_data):
            allowed.update((path, "site/" + path))
    return allowed


def files_digest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for folder in ("site", "data") for p in (root / folder).rglob("*")
            if p.is_file() and not p.is_symlink() and ".cache" not in p.parts}


def validate_release(root):
    """CI-equivalent offline publication gate; no source acquisition or provider secrets."""
    (root / ".cache").mkdir(exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in {
        "GH_TOKEN", "GITHUB_TOKEN", "GEMINI_API_KEY", "GOOGLE_MAPS_API_KEY",
        "GOOGLE_MAPS_BROWSER_KEY", "PUJA_SUGGEST_FORM_URL",
    }}
    env.update(AUTO_PUBLISH="false", LLM_ENABLED="false", PYTHONDONTWRITEBYTECODE="1")

    def run(*args):
        result = subprocess.run(args, cwd=root, env=env, timeout=600, check=False)
        if result.returncode:
            raise Blocked("approval validation failed: " + " ".join(args))

    py = sys.executable
    run(py, "-m", "food_safety.cli", "puja", "sources", "validate")
    run(py, "-m", "food_safety.cli", "validate")
    run(py, "-m", "food_safety.cli", "build")
    first = files_digest(root)
    run(py, "-m", "food_safety.cli", "build")
    if files_digest(root) != first:
        raise Blocked("non-deterministic publication build")
    run(py, "-m", "ruff", "check", ".")
    run(py, "-m", "pytest", "-q", "--tb=short", "--basetemp=.cache/pytest")
    run("node", "--test", *[str(p.relative_to(root)) for p in sorted(
        (root / "tests").glob("*.test.mjs")
    )])
    run(py, "scripts/verify_public_output.py")
    run(py, "scripts/stage_generated.py")
    run(py, "-m", "pip_audit", "--skip-editable", "--progress-spinner", "off",
        "--cache-dir", ".cache/audit")
    run("git", "diff", "--check")


def integrate(root, release_plan, validator=validate_release):
    """Only in a disposable main checkout. A conflict never touches remote refs."""
    if git(root, "rev-parse", "HEAD") != release_plan["main"]:
        raise Blocked("release checkout is not pinned to inspected main")
    if git(root, "status", "--porcelain"):
        raise Blocked("release checkout must be clean")
    if release_plan["already_released"]:
        return release_plan["main"]
    git(root, "merge", "--no-ff", "--no-commit", release_plan["develop"])
    # Only verified catalog input is merged. All derived output is rebuilt here.
    validator(root)
    canonical = catalog_paths(root)
    generated = derived_paths(root)
    paths = git(root, "diff", "HEAD", "--name-only").splitlines()
    for path in paths:
        if path not in canonical | generated:
            raise Blocked(f"unexpected generated path: {path}")
        if (root / path).is_symlink() or not (root / path).is_file():
            raise Blocked(f"invalid generated file: {path}")
        if path in canonical and git(root, "diff", release_plan["develop"], "--", path):
            raise Blocked("validation changed canonical approval data")
    if git(root, "ls-files", "--others", "--exclude-standard"):
        raise Blocked("unexpected untracked generated output")
    git(root, "add", "--", *paths)
    shas = ",".join(a["sha"] for a in release_plan["approvals"])
    git(root, "commit", "-m", "data: release Puja approvals", "-m", f"Puja-Approvals: {shas}")
    result = git(root, "rev-parse", "HEAD")
    if parents(root, result) != [release_plan["main"], release_plan["develop"]]:
        raise Blocked("release ancestry mismatch")
    return result


def publish(root, release_plan, sha):
    """Atomic non-force update: either both branches advance, or neither does."""
    if release_plan["already_released"]:
        return
    if parents(root, sha) != [release_plan["main"], release_plan["develop"]]:
        raise Blocked("publication requires the validated release merge")
    refs = git(root, "ls-remote", "origin", "refs/heads/main", "refs/heads/develop")
    current = {line.split()[1]: line.split()[0] for line in refs.splitlines()}
    if current != {"refs/heads/main": release_plan["main"],
                   "refs/heads/develop": release_plan["develop"]}:
        raise Blocked("main/develop advanced during validation; no branch was updated")
    git(root, "push", "--atomic", "origin", f"{sha}:refs/heads/main",
        f"{sha}:refs/heads/develop")


def sync_after_release(root, upstream):
    """Permit local FF only to a verifiable release merge already on production."""
    local = git(root, "rev-parse", "HEAD")
    if not ancestor(root, local, upstream):
        raise Blocked("local develop diverged; preserving unpublished work")
    match = RELEASE.fullmatch(message(root, upstream))
    ps = parents(root, upstream)
    if not match or len(ps) != 2:
        raise Blocked("upstream is not an approval release; manual sync required")
    git(root, "fetch", "origin", "main")
    if not ancestor(root, upstream, "origin/main") or not ancestor(root, local, ps[1]):
        raise Blocked("upstream release is not on production or does not contain local approval")
    expected = plan(root, ps[0], ps[1])
    if match[1].split(",") != [a["sha"] for a in expected["approvals"]]:
        raise Blocked("upstream release receipt mismatch")
    changed(root, ps[0], upstream, catalog_paths(root) | derived_paths(root))
    # Git's normal FF refuses overlapping dirty/untracked files; no stash/reset/force.
    git(root, "merge", "--ff-only", upstream)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sha", required=True)
    parser.add_argument("--publish", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    summary = ["## Puja approval release", f"Requested commit: `{args.sha}`"]
    try:
        if not re.fullmatch(r"[a-f0-9]{40}", args.sha):
            raise Blocked("invalid full commit SHA")
        if os.environ.get("APPROVAL_CI_RESULT") != "success":
            raise Blocked("approval CI did not succeed")
        if git(root, "rev-parse", "origin/develop") != args.sha and not ancestor(
            root, args.sha, "origin/main"
        ):
            raise Blocked("CI commit is no longer the develop tip")
        release_plan = plan(root, "origin/main", args.sha)
        for item in release_plan["approvals"]:
            summary.append(
                f"Approval: `{item['sha']}` / `{item['candidate']}` / `{item['pandal']}`"
            )
            summary.append("Files: " + ", ".join(f"`{p}`" for p in item["files"]))
        sha = integrate(root, release_plan)
        summary.append("Validation: passed" if not release_plan["already_released"]
                       else "Validation: already released; no duplicate change")
        if not release_plan["already_released"]:
            outputs = git(root, "diff", "--name-only", release_plan["main"], sha).splitlines()
            summary.append("Release files: " + ", ".join(f"`{p}`" for p in outputs))
        if args.publish:
            publish(root, release_plan, sha)
        summary.extend(["Result: " + ("RELEASED" if args.publish else "VALIDATED, NOT PUSHED"),
                        ("Resulting main SHA" if args.publish else "Unpushed release SHA")
                        + f": `{sha}`"])
    except Exception as exc:
        reason = str(exc) if isinstance(exc, Blocked) else type(exc).__name__
        summary.extend(["APPROVAL RELEASE BLOCKED", "Reason: " + reason,
                        "No automatic retry or protection bypass attempted."])
        print("\n".join(summary))
        raise SystemExit(1) from None
    finally:
        if path := os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(path).open("a") as stream:
                stream.write("\n".join(summary) + "\n")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
