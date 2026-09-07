import json
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest

from food_safety.config import ROOT, SourcePolicy
from food_safety.extract import article_text, text_hash
from food_safety.models import Event
from food_safety.storage import dump, envelope

AT = datetime(2026, 1, 3, tzinfo=UTC)
URL = "https://example.org/fixture"


@pytest.fixture
def fixture_html():
    return (Path(__file__).parent / "fixtures/inspection.html").read_text()


@pytest.fixture
def policy():
    return SourcePolicy(
        name="Synthetic fixture publisher", domain="example.org", tier="A", enabled=True, urls=[URL]
    )


@pytest.fixture
def record(fixture_html):
    title, text = article_text(fixture_html)
    fields = {
        "event_date": "2026-01-02",
        "area": "Example Area",
        "establishment_name": "Example Kitchen",
        "reported_observation": "Example Kitchen was inspected.",
        "reported_action": "Inspectors collected samples.",
    }
    return Event.model_validate(
        {
            "event_id": "WBFS-0123456789ab",
            "is_fixture": True,
            "reported_fact": {
                **fields,
                "evidence": {field: {"source_url": URL, "quote": text} for field in fields},
            },
            "sources": [
                {
                    "source_url": URL,
                    "source_title": title,
                    "source_publisher": "Synthetic fixture publisher",
                    "source_type": "official",
                    "tier": "A",
                    "retrieved_at": AT,
                    "text_sha256": text_hash(text),
                    "evidence_quote": text,
                    "evidence_context": text,
                }
            ],
            "verification_status": "SOURCE VERIFIED",
            "display_summary": (
                "Source reports a source-reported food-safety event involving "
                "Example Kitchen in Example Area."
            ),
            "review": {
                "reviewed_at": AT,
                "reviewer": "fixture-reviewer",
                "note": "Synthetic fixture only",
                "source_context_checked": True,
                "all_fields_supported": True,
            },
            "record_created_at": AT,
            "record_updated_at": AT,
            "history": [{"at": AT, "status": "SOURCE VERIFIED", "note": "Synthetic fixture only"}],
        }
    )


@pytest.fixture
def project(tmp_path):
    for name in ["config", "data"]:
        (tmp_path / name).mkdir()
    for name in ["pipeline.yml", "sources.yml"]:
        shutil.copyfile(ROOT / "config" / name, tmp_path / "config" / name)
    for name in ["events", "pending", "rejected"]:
        dump(tmp_path / "data" / f"{name}.json", envelope([], AT))
    for name in ["schema_version.json", "status.json"]:
        shutil.copyfile(ROOT / "data" / name, tmp_path / "data" / name)
    for path in ROOT.glob("*.md"):
        shutil.copyfile(path, tmp_path / path.name)
    return tmp_path


def enable_policy(project, policy):
    import yaml

    (project / "config/sources.yml").write_text(
        yaml.safe_dump({"sources": [policy.model_dump(mode="json")]})
    )


class FakeFetcher:
    def __init__(self, html):
        self.html = html

    def article(self, url):
        if isinstance(self.html, Exception):
            raise self.html
        return url, self.html


def load(project, name):
    return json.loads((project / "data" / f"{name}.json").read_text())
