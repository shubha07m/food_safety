"""Owner-authored GitHub approvals and bounded static catalog publication."""

import json
import subprocess
from pathlib import Path

from ..storage import dump
from .leads import canonical
from .models import PandalRecord, SourceSpec
from .review_queue import OWNER, REPO, parse_issue_body

OVERLAY = "config/puja-approved.json"
RECEIPT = ".cache/puja/published_issues.json"


def github(method, endpoint, payload=None):
    args = ["gh", "api", "--method", method, endpoint]
    if payload is not None:
        args += ["--input", "-"]
    result = subprocess.run(
        args,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        timeout=25,
        check=False,
    )
    if result.returncode:
        # gh stderr may include request data; never forward it into UI or logs.
        raise RuntimeError("github_request_failed")
    return json.loads(result.stdout) if result.stdout.strip() else {}


def owner_login(api=github):
    if api("GET", "user").get("login", "").casefold() != OWNER.casefold():
        raise ValueError("github_owner_login_required")


def submit_approval(payload, api=github):
    from .review_queue import issue_body

    body = issue_body(payload)
    parse_issue_body(body)
    owner_login(api)
    result = api(
        "POST",
        f"repos/{REPO}/issues",
        {"title": f"Puja approval {payload['candidate_id']}", "body": body},
    )
    if not isinstance(result.get("number"), int):
        raise ValueError("approval_not_persisted")
    return result["number"]


def approval_issues(api=github):
    page = 1
    while page <= 10:
        rows = api("GET", f"repos/{REPO}/issues?state=open&per_page=100&page={page}")
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


def publish_approved(root: Path, api=github):
    """One invalid issue is skipped. Only a fully valid overlay reaches Git."""
    from .pipeline import load_config

    overlay = _read_overlay(root)
    existing = {a["issue_number"] for a in overlay["approvals"]}
    applied, invalid, new = [], [], 0
    try:
        issues = list(approval_issues(api))
    except RuntimeError:
        # Publication waits for the next run; unrelated static refreshes continue.
        return {"approved_added": 0, "already_published": 0, "invalid": [], "sync": "unavailable"}
    for issue in issues:
        number = issue["number"]
        if number in existing:
            applied.append(number)
            continue
        try:
            value = parse_issue_body(issue.get("body"))
            if issue["title"] != f"Puja approval {value['candidate_id']}":
                raise ValueError("issue_identity_mismatch")
            record = PandalRecord.model_validate(value["record"])
            spec = SourceSpec.model_validate(value["source"])
            if spec.source_id != "approved-" + value["candidate_id"]:
                prior = next(
                    (
                        s
                        for s in load_config(root, approval_overlay=overlay).sources
                        if s.source_id == spec.source_id
                    ),
                    None,
                )
                if (
                    not prior
                    or prior.region_id != spec.region_id
                    or canonical(str(prior.url)) != canonical(str(spec.url))
                ):
                    raise ValueError("source_identity_mismatch")
            if any(
                a["record"]["pandal_id"] == record.pandal_id
                and a["candidate_id"] != value["candidate_id"]
                for a in overlay["approvals"]
            ):
                raise ValueError("approval_record_collision")
            if any(
                a["record"]["pandal_id"] == record.pandal_id and a["issue_number"] > number
                for a in overlay["approvals"]
            ):
                raise ValueError("newer_approval_already_published")
            trial = {
                **overlay,
                "approvals": [*overlay["approvals"], {"issue_number": number, **value}],
            }
            load_config(root, approval_overlay=trial)
            overlay = trial
            existing.add(number)
            applied.append(number)
            new += 1
        except Exception as exc:
            invalid.append({"issue_number": number, "reason": type(exc).__name__})
    if new:
        dump(root / OVERLAY, overlay)
    dump(root / RECEIPT, {"issue_numbers": sorted(set(applied))})
    return {"approved_added": new, "already_published": len(applied) - new, "invalid": invalid}


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
