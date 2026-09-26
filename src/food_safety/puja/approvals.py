"""Frozen private decisions, applied directly to the normal regional catalogs."""

import fcntl
import hashlib
import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path

import yaml

from ..storage import dump
from .leads import canonical, norm
from .models import PandalRecord, SourceSpec
from .review_queue import candidate_id, load_decisions, save_decision, validate_approval

OUTBOX = ".cache/puja/approval_outbox"
REPORTED = ".cache/puja/approval_errors.json"
EDIT = ".cache/puja/catalog_edit.json"


def catalog_paths(root):
    from .regions import load_regions

    return {"config/puja.yml"} | {
        r.catalog_config for r in load_regions(root).regions if r.catalog_config
    }


def represented(root, payload):
    """The reviewed revision in the actual catalog is the durable receipt."""
    from .pipeline import load_config

    config = load_config(root)
    record = next(
        (p for p in config.published if p.pandal_id == payload["record"]["pandal_id"]), None
    )
    return bool(
        record
        and record.region_id == payload["record"]["region_id"]
        and any(
            canonical(str(s.source_url)) == canonical(payload["source"]["url"])
            and s.source_revision_id == payload["source_revision"]
            for s in record.sources
        )
        and any(
            s.source_id == payload["source"]["source_id"]
            and canonical(str(s.url)) == canonical(payload["source"]["url"])
            for s in config.sources
        )
    )


def canonical_changes(root, payload):
    """Prepare and validate normal YAML in memory before touching any file."""
    from .pipeline import load_config
    from .regions import get_region

    validate_approval(payload)
    if represented(root, payload):
        return {}
    record = PandalRecord.model_validate(payload["record"])
    source = SourceSpec.model_validate(payload["source"])
    config = load_config(root)
    previous = next((p for p in config.published if p.pandal_id == record.pandal_id), None)
    if previous and (
        previous.region_id != record.region_id
        or previous.last_verified_at > record.last_verified_at
    ):
        raise ValueError("catalog_changed_since_approval")
    if any(
        p.pandal_id != record.pandal_id
        and p.region_id == record.region_id
        and norm(record.name) in {norm(p.name), *(norm(a) for a in p.aliases)}
        for p in config.published
    ):
        raise ValueError("catalog_identity_collision")
    prior_source = next((s for s in config.sources if s.source_id == source.source_id), None)
    if prior_source and (
        prior_source.region_id != source.region_id
        or canonical(str(prior_source.url)) != canonical(str(source.url))
    ):
        raise ValueError("source_identity_mismatch")
    path = get_region(root, record.region_id).catalog_config or "config/puja.yml"
    originals = {p: yaml.safe_load((root / p).read_text()) for p in catalog_paths(root)}
    changes = {}
    for section, key, model in (
        ("published", "pandal_id", record),
        ("sources", "source_id", source),
    ):
        identity = getattr(model, key)
        owners = [
            p for p, doc in originals.items() if any(r[key] == identity for r in doc[section])
        ]
        if len(owners) > 1:
            raise ValueError("duplicate_catalog_identity")
        target = owners[0] if owners else path
        doc = changes.setdefault(target, originals[target])
        value = model.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
        rows = doc[section]
        found = next((i for i, row in enumerate(rows) if row[key] == identity), None)
        if found is None:
            rows.append(value)
        else:
            rows[found] = value
    load_config(root, catalog_overrides=changes)
    return {
        p: yaml.safe_dump(doc, allow_unicode=True, sort_keys=False) for p, doc in changes.items()
    }


def _git(root, *args):
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            timeout=90,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("git_" + args[0] + "_unavailable") from exc
    if result.returncode:
        # Git/provider output can contain account details; report the failed operation only.
        raise RuntimeError("git_" + args[0] + "_failed")
    return result.stdout.strip()


@contextmanager
def _lock(root):
    path = root / ".cache/puja/approval.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("another_approval_is_running") from exc
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def _deliver(root, payload):
    validate_approval(payload)
    if Path(_git(root, "rev-parse", "--show-toplevel")).resolve() != root.resolve():
        raise ValueError("review_requires_repository_root")
    if _git(root, "branch", "--show-current") != "develop":
        raise ValueError("approval_requires_develop")
    for name in ("MERGE_HEAD", "CHERRY_PICK_HEAD", "rebase-merge", "rebase-apply"):
        if (root / _git(root, "rev-parse", "--git-path", name)).exists():
            raise ValueError("git_operation_in_progress")
    if _git(root, "diff", "--cached", "--name-only"):
        raise ValueError("staged_changes_preserved")
    paths = catalog_paths(root)
    _recover_edit(root, paths)
    if _git(root, "status", "--porcelain", "--", "config/regions.yml", *sorted(paths)):
        raise ValueError("catalog_local_changes_preserved")
    for path in paths:
        if (root / path).is_symlink():
            raise ValueError("catalog_symlink_not_supported")
        _git(root, "ls-files", "--error-unmatch", "--", path)
    _git(root, "fetch", "origin", "develop")
    _git(root, "merge-base", "--is-ancestor", "origin/develop", "HEAD")
    # Retry may find an earlier approval commit whose push failed. Never push
    # unrelated local code commits as a side effect of an editorial action.
    for commit in _git(root, "rev-list", "origin/develop..HEAD").splitlines():
        body = _git(root, "show", "-s", "--format=%B", commit)
        if not re.fullmatch(
            r"data: approve Puja pc-[a-f0-9]{20}\n\nPuja-Revision: [a-f0-9]{64}", body
        ):
            raise ValueError("unpublished_non_curation_commits_preserved")
        changed = set(
            _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", commit).splitlines()
        )
        if not changed or changed - paths:
            raise ValueError("unpublished_non_curation_commits_preserved")
    changes = canonical_changes(root, payload)
    if changes:
        before = {p: (root / p).read_text() for p in changes}
        head = _git(root, "rev-parse", "HEAD")
        dump(root / EDIT, {"head": head, "before": before, "after": changes})
        try:
            for path, text in changes.items():
                (root / path).write_text(text)
            _git(
                root,
                "commit",
                "--only",
                "-m",
                f"data: approve Puja {payload['candidate_id']}",
                "-m",
                f"Puja-Revision: {payload['source_revision']}",
                "--",
                *sorted(changes),
            )
        except (OSError, RuntimeError):
            _recover_edit(root, paths)
            raise
        (root / EDIT).unlink()
    commit = _git(root, "rev-parse", "HEAD")
    if commit != _git(root, "rev-parse", "origin/develop"):
        _git(root, "push", "origin", "HEAD:refs/heads/develop")
    return commit


def _recover_edit(root, allowed):
    """Recover only our exact interrupted write; never overwrite an owner's edit."""
    path = root / EDIT
    if not path.exists():
        return
    edit = json.loads(path.read_text())
    before, after = edit["before"], edit["after"]
    if set(before) != set(after) or not set(after) <= allowed:
        raise ValueError("interrupted_catalog_edit_invalid")
    for name in after:
        if (root / name).is_symlink() or (root / name).read_text() not in (
            before[name],
            after[name],
        ):
            raise ValueError("interrupted_catalog_edit_changed_by_owner")
    if _git(root, "rev-parse", "HEAD") == edit["head"]:
        for name in before:
            (root / name).write_text(before[name])
    elif any(_git(root, "show", f"HEAD:{name}") != after[name].strip() for name in after):
        raise ValueError("interrupted_catalog_commit_changed")
    path.unlink()


def deliver_approval(root, payload):
    with _lock(root):
        return _deliver(root, payload)


def _report_once(root, path, reason):
    reported_path = root / REPORTED
    reported = json.loads(reported_path.read_text()) if reported_path.exists() else {}
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    if reported.get(path.stem) != [fingerprint, reason]:
        print(f"Saved approval {path.stem}: {reason}; retained for retry.", flush=True)
        reported[path.stem] = [fingerprint, reason]
        dump(reported_path, reported)


def queue_approval(root, item, payload, submit=None):
    """Save the owner decision first, then commit only canonical Puja files."""
    validate_approval(payload)
    with _lock(root):
        decision = load_decisions(root).get(item["candidate_id"], {})
        if decision.get("decision") == "reject":
            raise ValueError("rejected_decision_preserved")
        path = root / OUTBOX / (item["candidate_id"] + ".json")
        if not path.exists():
            dump(
                path,
                {
                    "candidate": {
                        "candidate_id": item["candidate_id"],
                        "source_revision": item["source_revision"],
                    },
                    "payload": payload,
                },
            )
        frozen = json.loads(path.read_text())
        if frozen["payload"] != payload:
            raise ValueError("approved_revision_is_frozen")
        if decision.get("decision") != "approved":
            save_decision(root, frozen["candidate"], "approved", tier=payload["tier"])
        if frozen.get("canonical_commit"):
            return frozen["canonical_commit"]
        try:
            commit = submit(payload) if submit else _deliver(root, payload)
        except (RuntimeError, ValueError, OSError) as exc:
            reason = str(exc) if type(exc) in (ValueError, RuntimeError) else type(exc).__name__
            _report_once(root, path, reason.split("\n")[0][:100])
            return None
        # Legacy issue/request fields remain private history, never transport inputs.
        dump(path, {**frozen, "canonical_commit": commit})
        return commit


def resume_approvals(root, submit=None):
    decisions = load_decisions(root)
    for path in sorted((root / OUTBOX).glob("pc-*.json")):
        if decisions.get(path.stem, {}).get("decision") == "reject":
            continue
        try:
            value = json.loads(path.read_text())
            payload = validate_approval(value["payload"])
            if (
                payload["candidate_id"] != path.stem
                or value["candidate"]["candidate_id"] != path.stem
                or value["candidate"]["source_revision"] != payload["source_revision"]
            ):
                raise ValueError("saved_approval_identity_mismatch")
            if not value.get("canonical_commit"):
                queue_approval(root, value["candidate"], payload, submit)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            # Do not print validation input values or malformed private file contents.
            reason = str(exc) if type(exc) is ValueError else type(exc).__name__
            _report_once(root, path, reason.split("\n")[0][:100])


def restore_approvals(root):
    """A fresh laptop recognizes reviewed records from the canonical Git catalog."""
    from .pipeline import load_config

    known = load_decisions(root)
    for record in load_config(root).published:
        for evidence in record.sources:
            if not evidence.source_revision_id:
                continue
            key = candidate_id(record.region_id, str(evidence.source_url), record.name)
            if key not in known:
                save_decision(
                    root,
                    {"candidate_id": key, "source_revision": evidence.source_revision_id},
                    "approved",
                )
                known[key] = True
