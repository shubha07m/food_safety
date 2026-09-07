import pytest
from pydantic import ValidationError

from food_safety.classify import (
    classify_action,
    classify_business_format,
    classify_establishment_context,
    display_summary,
)
from food_safety.models import DerivedContext


def test_explicit_action_classification():
    assert classify_action("Officials collected samples for analysis.") == "sample collected"
    assert classify_action("The team destroyed the retained stock.") == "food discarded / destroyed"
    assert classify_action("Officials reviewed the premises.") == "not reported"


def test_explicit_establishment_context():
    assert (
        classify_establishment_context("Inspection at the mall food court")
        == "mall / food court"
    )
    assert classify_establishment_context("A sweet shop was inspected") == "sweet shop / bakery"
    assert classify_establishment_context("A business was visited") == "unknown"


def test_explicit_business_format():
    assert classify_business_format("The outlet is part of the chain") == "chain_group"
    assert classify_business_format("A local restaurant was inspected") == "unknown"


def test_menu_context_requires_allowed_reviewed_evidence():
    source = "https://example.org/menu"
    context = DerivedContext(
        menu_context="mixed",
        menu_context_source=source,
        menu_context_method="establishment_website",
        menu_context_confidence="high",
        menu_context_reviewed=True,
    )
    assert context.menu_context == "mixed"
    with pytest.raises(ValidationError):
        DerivedContext(menu_context="non_veg", menu_context_method="name_guess")
    with pytest.raises(ValidationError):
        DerivedContext(menu_context="non_veg")


def test_display_summary_uses_only_structured_fields(record):
    summary = display_summary(record.reported_fact, record.derived_context)
    assert record.reported_fact.establishment_name in summary
    assert record.reported_fact.area in summary
    assert "guilty" not in summary.casefold()
