import json

import pytest
from conftest import AT

from food_safety.build import aggregates, build, csv_text, validate
from food_safety.config import ROOT
from food_safety.storage import save_events


def test_graph_totals(record):
    result = aggregates([record])
    for key in ["timeline", "areas", "actions", "owners", "menus"]:
        assert sum(result[key].values()) == result["total"] == 1
    assert result["menus"] == {"unknown": 1}


def test_zero_build(project):
    build(project)
    assert json.loads((project / "site/data/events.json").read_text())["record_count"] == 0
    assert not (project / "site/data/pending.json").exists()
    assert (project / "site/policies/disclaimer.html").exists()


def test_public_fixture_build_rejected(project, record):
    save_events(project, "events", [record], AT)
    with pytest.raises(ValueError, match="fixture_not_public"):
        build(project)


def test_csv_preserves_context_and_blocks_formulas(record):
    record.reported_fact.establishment_name = "=HYPERLINK(1)"
    text = csv_text([record])
    assert "'=HYPERLINK" in text
    assert "Inclusion is not a finding of wrongdoing" in text


def test_incomplete_transaction_blocks(project):
    (project / "data/.transaction.json").write_text("{}")
    with pytest.raises(ValueError, match="unfinished"):
        validate(project)


def test_no_demo_in_production():
    records = json.loads((ROOT / "data/events.json").read_text())["records"]
    assert all(not record["is_fixture"] for record in records)
