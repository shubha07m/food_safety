"""Deterministic additive migration; IDs, evidence and historical timestamps survive."""

import json
from urllib.parse import urlsplit

from . import SCHEMA_VERSION, __version__
from .config import sources
from .models import Event
from .storage import dump, envelope


def migrate(root):
    from datetime import datetime

    languages = {
        policy.domain: policy.language
        for policy in sources(root)
        if policy.language in {"en", "bn"}
    }
    for name in ["events", "pending", "rejected", "retired"]:
        path = root / "data" / f"{name}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        if name in {"events", "pending"}:
            for record in data["records"]:
                for source in record.get("sources", []):
                    domain = urlsplit(source["source_url"]).hostname
                    if domain in languages:
                        source["source_language"] = languages[domain]
            data["records"] = [
                Event.model_validate(r).model_dump(mode="json") for r in data["records"]
            ]
        value = envelope(data["records"], datetime.fromisoformat(data["generated_at"]))
        dump(path, value)
    dump(
        root / "data/schema_version.json",
        {"schema_version": SCHEMA_VERSION, "pipeline_version": __version__},
    )
    if not (root / "data/compliance.json").exists():
        baseline = json.loads((root / "data/events.json").read_text())
        dump(
            root / "data/compliance.json",
            envelope([], datetime.fromisoformat(baseline["generated_at"])),
        )
