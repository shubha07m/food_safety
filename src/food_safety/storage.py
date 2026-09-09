import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from . import CONTEXT, SCHEMA_VERSION, __version__
from .models import Dataset, Event


def now():
    return datetime.now(UTC)


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    temporary.replace(path)


def envelope(records, at):
    return {
        "generated_at": at.isoformat(),
        "schema_version": SCHEMA_VERSION,
        "pipeline_version": __version__,
        "record_count": len(records),
        "context_notice": CONTEXT,
        "records": records,
    }


def read_events(root, name):
    path = root / "data" / f"{name}.json"
    if name == "pending" and not path.exists():
        return []
    return Dataset.model_validate_json(path.read_text()).records


def read_rejected(root):
    path = root / "data/rejected.json"
    return json.loads(path.read_text()) if path.exists() else envelope([], now())


def save_events(root, name, records, at):
    value = envelope(
        [r.model_dump(mode="json") for r in sorted(records, key=lambda r: r.event_id)], at
    )
    Dataset.model_validate(value)
    path = root / "data" / f"{name}.json"
    if path.exists() and json.loads(path.read_text()).get("records") == value["records"]:
        return  # A scan is not a new dataset version when approved rows did not change.
    dump(path, value)


def transition(root, event, status, note, at, review=None):
    previous = event.model_dump(mode="json")
    digest = hashlib.sha256(json.dumps(previous, sort_keys=True).encode()).hexdigest()
    dump(root / "data/history" / event.event_id / f"{digest}.json", previous)
    data = dict(previous)
    data.update(
        verification_status=status,
        verification_notes=note,
        record_updated_at=at.isoformat(),
        review=review,
    )
    if status not in {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"}:
        data.update(
            publication_status="superseded" if status == "SUPERSEDED" else "suspended",
            evidence_support_status="withdrawn" if status == "SOURCE WITHDRAWN" else "needs_review",
            reviewer_hold=True,
        )
    data["history"] = [
        *previous["history"],
        {
            "at": at.isoformat(),
            "status": status,
            "note": note,
            "previous_record_sha256": digest,
        },
    ]
    return Event.model_validate(data)


def transaction(root, events, pending, rejected, at):
    # An interrupted multi-file update blocks validation/build until explicitly recovered.
    marker = root / "data/.transaction.json"
    if marker.exists():
        raise ValueError("unfinished_data_transaction: restore reviewed files using Git")
    ids = [r.event_id for r in [*events, *pending]]
    if len(ids) != len(set(ids)):
        raise ValueError("event_in_multiple_queues")
    Dataset.model_validate(envelope([r.model_dump(mode="json") for r in events], at))
    Dataset.model_validate(envelope([r.model_dump(mode="json") for r in pending], at))
    dump(marker, {"started_at": at.isoformat()})
    save_events(root, "events", events, at)
    save_events(root, "pending", pending, at)
    dump(root / "data/rejected.json", envelope(rejected, at))
    marker.unlink()
