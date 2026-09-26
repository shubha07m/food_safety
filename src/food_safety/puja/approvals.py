"""Private owner decisions, public-safe Git requests, and static publication."""

import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path

from ..storage import dump
from .leads import canonical
from .models import PandalRecord, SourceEvidence, SourceSpec
from .review_queue import OWNER, REPO, parse_issue_body, validate_approval

OVERLAY = "config/puja-approved.json"
RECEIPT = ".cache/puja/published_issues.json"
QUEUE_BRANCH = "puja-approvals"
QUEUE_DIR = "config/puja-requests"
OUTBOX = ".cache/puja/approval_outbox"
REPORTED = ".cache/puja/approval_errors.json"


class GithubAPIError(RuntimeError):
    def __init__(self, status):
        super().__init__("github_request_failed")
        self.status = status


def github(method, endpoint, payload=None):
    args = ["gh", "api", "--method", method, endpoint]
    if payload is not None:
        args += ["--input", "-"]
    try:
        result = subprocess.run(
            args,
            input=json.dumps(payload) if payload is not None else None,
            text=True,
            capture_output=True,
            timeout=25,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("github_request_unavailable") from exc
    if result.returncode:
        # Never forward provider text. Only retain the HTTP status for 404 handling.
        match = re.search(r"HTTP (\d{3})", result.stderr)
        raise GithubAPIError(int(match.group(1)) if match else None)
    return json.loads(result.stdout) if result.stdout.strip() else {}


def owner_login(api=github):
    if api("GET", "user").get("login", "").casefold() != OWNER.casefold():
        raise ValueError("github_owner_login_required")


def _optional(api, endpoint):
    try:
        return api("GET", endpoint)
    except GithubAPIError as exc:
        if exc.status == 404:
            return None
        raise


def request_path(candidate_id):
    if not re.fullmatch(r"pc-[a-f0-9]{20}", candidate_id):
        raise ValueError("approval_candidate_id_invalid")
    return f"{QUEUE_DIR}/{candidate_id}.json"


def _contents(value):
    if value.get("encoding") != "base64" or not isinstance(value.get("content"), str):
        raise ValueError("approval_request_encoding_invalid")
    body = base64.b64decode("".join(value["content"].split()), validate=True)
    if len(body) > 60000:
        raise ValueError("approval_payload_too_large")
    return validate_approval(json.loads(body))


def deliver_approval(payload, api=github):
    """Create one immutable, publication-safe Git file; never create an Issue."""
    validate_approval(payload)
    owner_login(api)
    branch = _optional(api, f"repos/{REPO}/git/ref/heads/{QUEUE_BRANCH}")
    if branch is None:
        main = api("GET", f"repos/{REPO}/git/ref/heads/main")
        try:
            api(
                "POST",
                f"repos/{REPO}/git/refs",
                {"ref": f"refs/heads/{QUEUE_BRANCH}", "sha": main["object"]["sha"]},
            )
        except GithubAPIError as exc:
            if exc.status != 422:  # Another owner session may have created it.
                raise
    path = request_path(payload["candidate_id"])
    endpoint = f"repos/{REPO}/contents/{path}?ref={QUEUE_BRANCH}"
    prior = _optional(api, endpoint)
    if prior is not None:
        if _contents(prior) != payload:
            raise ValueError("approval_request_identity_conflict")
        return path
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    api(
        "PUT",
        f"repos/{REPO}/contents/{path}",
        {
            "message": f"data: queue reviewed Puja {payload['candidate_id']}",
            "content": base64.b64encode((body + "\n").encode()).decode(),
            "branch": QUEUE_BRANCH,
        },
    )
    # A lost response is recovered by reading this deterministic path on retry.
    return path


def approval_issues(api=github, state="open"):
    page = 1
    while page <= 10:
        rows = api("GET", f"repos/{REPO}/issues?state={state}&per_page=100&page={page}")
        if not isinstance(rows, list):
            raise ValueError("invalid_issue_listing")
        for row in rows:
            if (
                not row.get("pull_request")
                and row.get("user", {}).get("login", "").casefold() == OWNER.casefold()
                and str(row.get("title", "")).startswith("Puja approval pc-")
            ):
                yield row
        if len(rows) < 100:
            break
        page += 1


def queue_approval(root, item, payload, submit=None):
    """Freeze approval before Git delivery; legacy issued approvals stay issued."""
    from .review_queue import save_decision

    validate_approval(payload)
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
    save_decision(root, frozen["candidate"], "approved", tier=frozen["payload"]["tier"])
    if frozen.get("issue_number"):
        # These were already delivered by the retired transport. The publisher
        # consumes and closes them once; do not also queue a Git request.
        return f"legacy issue {frozen['issue_number']}"
    send = submit or deliver_approval
    try:
        request = frozen.get("request_path") or send(frozen["payload"])
    except RuntimeError:
        return None
    except ValueError as exc:
        _report_once(root, path, str(exc).split("\n")[0][:100])
        return None
    dump(path, {**frozen, "request_path": request})
    save_decision(
        root,
        frozen["candidate"],
        "approved",
        request_path=request,
        tier=frozen["payload"]["tier"],
    )
    return request


def _repair_saved_approval(root, path, value):
    """Repair the known old-source revision omission without changing facts."""
    from .pipeline import load_config
    from .review_queue import load_decisions

    payload = value["payload"]
    if value.get("issue_number") or payload.get("tier") != "source_listed":
        raise ValueError("approval_migration_not_applicable")
    if load_decisions(root).get(path.stem, {}).get("decision") != "approved":
        raise ValueError("approval_decision_not_confirmed")
    if payload.get("candidate_id") != path.stem or value["candidate"][
        "source_revision"
    ] != payload.get("source_revision"):
        raise ValueError("approval_identity_mismatch")
    record = PandalRecord.model_validate(payload["record"])
    source = SourceSpec.model_validate(payload["source"])
    config = load_config(root)
    base = next((p for p in config.published if p.pandal_id == record.pandal_id), None)
    known_source = next((s for s in config.sources if s.source_id == source.source_id), None)
    if not base or not known_source or base.region_id != record.region_id:
        raise ValueError("approval_migration_identity_unconfirmed")
    if str(known_source.url) != str(source.url) or known_source.region_id != source.region_id:
        raise ValueError("approval_migration_source_mismatch")
    before = base.model_dump(mode="json")
    after = record.model_dump(mode="json")
    if {k: v for k, v in before.items() if k != "last_verified_at"} != {
        k: v for k, v in after.items() if k != "last_verified_at"
    }:
        raise ValueError("approval_migration_facts_differ")
    if len(record.sources) >= 10:
        raise ValueError("approval_migration_source_limit")
    old = next((s for s in record.sources if str(s.source_url) == str(source.url)), None)
    if old is None:
        raise ValueError("approval_migration_source_missing")
    attestation = SourceEvidence(
        evidence_kind="owner_attestation",
        source_url=source.url,
        source_title=old.source_title,
        publisher=source.publisher,
        quote=(
            "Owner approved this submitted Puja identity and region; "
            "source text was not automatically verified."
        ),
        source_revision_id=payload["source_revision"],
    )
    repaired = {
        **payload,
        "record": {**after, "sources": [*after["sources"], attestation.model_dump(mode="json")]},
    }
    validate_approval(repaired)
    # Keep the exact original private payload for recovery before changing it.
    backup = root / ".cache/puja/approval_backups" / path.name
    if not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        backup.write_bytes(path.read_bytes())
    dump(path, {**value, "payload": repaired})
    return repaired


def migrate_outbox(root):
    """Idempotently repair only the four provable legacy revision omissions."""
    repaired, invalid = [], []
    for path in sorted((root / OUTBOX).glob("pc-*.json")):
        try:
            value = json.loads(path.read_text())
            validate_approval(value["payload"])
        except ValueError as exc:
            if str(exc) == "approval_evidence_missing":
                try:
                    _repair_saved_approval(root, path, value)
                    repaired.append(path.stem)
                    continue
                except (OSError, ValueError, KeyError, TypeError) as repair_exc:
                    invalid.append(
                        (
                            path.stem,
                            type(repair_exc).__name__ + ":" + str(repair_exc).split("\n")[0][:100],
                        )
                    )
            else:
                invalid.append(
                    (path.stem, type(exc).__name__ + ":" + str(exc).split("\n")[0][:100])
                )
        except (OSError, KeyError, TypeError) as exc:
            invalid.append((path.stem, type(exc).__name__))
    return {"repaired": repaired, "invalid": invalid}


def _report_once(root, path, reason):
    reported_path = root / REPORTED
    reported = json.loads(reported_path.read_text()) if reported_path.exists() else {}
    candidate_id = path.stem
    fingerprint = hashlib.sha256(path.read_bytes()).hexdigest()
    if reported.get(candidate_id) != [fingerprint, reason]:
        print(f"Saved approval {candidate_id} needs review: {reason}; retained.", flush=True)
        reported[candidate_id] = [fingerprint, reason]
        dump(reported_path, reported)


def resume_approvals(root, submit=None):
    report = migrate_outbox(root)
    for candidate_id, reason in report["invalid"]:
        _report_once(root, root / OUTBOX / (candidate_id + ".json"), reason)
    for path in sorted((root / OUTBOX).glob("pc-*.json")):
        if path.stem in {name for name, _ in report["invalid"]}:
            continue
        value = json.loads(path.read_text())
        if not value.get("issue_number") and not value.get("request_path"):
            queue_approval(root, value["candidate"], value["payload"], submit)


def restore_approvals(root, api=github):
    """A fresh laptop recovers delivered decisions without copying OAuth tokens."""
    from .review_queue import load_decisions, save_decision

    known = load_decisions(root)
    try:
        issues = list(approval_issues(api, state="all"))
    except RuntimeError:
        issues = []
    for issue in issues:
        try:
            value = parse_issue_body(issue.get("body"))
        except (ValueError, TypeError):
            continue
        if value["candidate_id"] not in known:
            save_decision(root, value, "approved", issue_number=issue["number"], tier=value["tier"])
            known[value["candidate_id"]] = True
    try:
        requests = queued_requests(api)
    except (RuntimeError, ValueError):
        requests = []
    for path, value, error in requests:
        if error is None and value["candidate_id"] not in known:
            save_decision(root, value, "approved", request_path=path, tier=value["tier"])
            known[value["candidate_id"]] = True


def _read_overlay(root):
    path = root / OVERLAY
    value = (
        json.loads(path.read_text())
        if path.exists()
        else {"schema_version": "puja-approvals-1", "approvals": []}
    )
    if value.get("schema_version") != "puja-approvals-1" or not isinstance(
        value.get("approvals"), list
    ):
        raise ValueError("invalid_approval_overlay")
    return value


def queued_requests(api=github):
    """Read only immutable public-safe request files from the dedicated Git ref."""
    directory = _optional(api, f"repos/{REPO}/contents/{QUEUE_DIR}?ref={QUEUE_BRANCH}")
    if directory is None:
        return []
    if not isinstance(directory, list) or len(directory) >= 1000:
        raise ValueError("approval_request_directory_invalid")
    rows = []
    for entry in sorted(directory, key=lambda row: row.get("path", "")):
        path = entry.get("path", "")
        try:
            if entry.get("type") != "file" or path != request_path(Path(path).stem):
                raise ValueError("approval_request_path_invalid")
            item = api("GET", f"repos/{REPO}/contents/{path}?ref={QUEUE_BRANCH}")
            value = _contents(item)
            if value["candidate_id"] != Path(path).stem:
                raise ValueError("approval_request_identity_mismatch")
            rows.append((path, value, None))
        except (RuntimeError, ValueError, TypeError, KeyError) as exc:
            rows.append((path, None, type(exc).__name__ + ":" + str(exc).split("\n")[0][:100]))
    return rows


def publish_approved(root: Path, api=github):
    """Consume Git requests plus already-issued legacy approvals independently."""
    from .pipeline import load_config

    overlay = _read_overlay(root)
    existing = {a["candidate_id"]: a for a in overlay["approvals"]}
    applied_issues, invalid, new = [], [], 0
    issue_online = True
    try:
        issues = list(approval_issues(api))
    except RuntimeError:
        issues = []
        issue_online = False
    queue_online = True
    try:
        requests = queued_requests(api)
    except (RuntimeError, ValueError):
        requests = []
        queue_online = False
    if not issues and not requests:
        return {
            "approved_added": 0,
            "already_published": 0,
            "invalid": [],
            "sync": "empty" if issue_online and queue_online else "unavailable",
        }
    already = 0
    items = [("issue", issue["number"], issue, None) for issue in issues]
    items.extend(("request", path, value, error) for path, value, error in requests)
    for kind, identity, raw, read_error in items:
        if read_error:
            invalid.append({"request": identity, "reason": read_error})
            continue
        try:
            value = parse_issue_body(raw.get("body")) if kind == "issue" else raw
            validate_approval(value)
            if kind == "issue" and raw["title"] != f"Puja approval {value['candidate_id']}":
                raise ValueError("issue_identity_mismatch")
            if value["candidate_id"] in existing:
                prior = existing[value["candidate_id"]]
                if prior["source_revision"] != value["source_revision"]:
                    raise ValueError("approved_revision_conflict")
                already += 1
                if kind == "issue":
                    applied_issues.append(identity)
                continue
            record = PandalRecord.model_validate(value["record"])
            spec = SourceSpec.model_validate(value["source"])
            if spec.source_id != "approved-" + value["candidate_id"]:
                prior_spec = next(
                    (
                        s
                        for s in load_config(root, approval_overlay=overlay).sources
                        if s.source_id == spec.source_id
                    ),
                    None,
                )
                if (
                    not prior_spec
                    or prior_spec.region_id != spec.region_id
                    or canonical(str(prior_spec.url)) != canonical(str(spec.url))
                ):
                    raise ValueError("source_identity_mismatch")
            if any(
                a["record"]["pandal_id"] == record.pandal_id
                and a["candidate_id"] != value["candidate_id"]
                for a in overlay["approvals"]
            ):
                raise ValueError("approval_record_collision")
            approved = {**value, ("issue_number" if kind == "issue" else "request_path"): identity}
            trial = {**overlay, "approvals": [*overlay["approvals"], approved]}
            load_config(root, approval_overlay=trial)
            overlay = trial
            existing[value["candidate_id"]] = approved
            new += 1
            if kind == "issue":
                applied_issues.append(identity)
        except (ValueError, KeyError, TypeError) as exc:
            invalid.append(
                {kind: identity, "reason": type(exc).__name__ + ":" + str(exc).split("\n")[0][:100]}
            )
    if new:
        dump(root / OVERLAY, overlay)
    dump(root / RECEIPT, {"issue_numbers": sorted(set(applied_issues))})
    return {"approved_added": new, "already_published": already, "invalid": invalid}


def close_published(root: Path, api=github):
    """Only after the generated-data commit/push step has completed."""
    receipt = root / RECEIPT
    if not receipt.exists():
        return {"closed": 0}
    numbers = json.loads(receipt.read_text())["issue_numbers"]
    closed = 0
    for number in numbers:
        try:
            api("PATCH", f"repos/{REPO}/issues/{number}", {"state": "closed"})
            closed += 1
        except RuntimeError:
            pass  # Retry on the next scheduled run; idempotent overlay prevents duplication.
    return {"closed": closed, "pending": len(numbers) - closed}
