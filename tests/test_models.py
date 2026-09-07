import pytest
from pydantic import ValidationError

from food_safety.models import Event


def test_valid_record(record):
    assert Event.model_validate(record.model_dump()).event_id == record.event_id


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(sources=[]),
        lambda d: d["sources"][0].update(source_url="javascript:alert(1)"),
        lambda d: d.update(verification_status="VERIFIED"),
        lambda d: d["reported_fact"].update(event_date="2026-02-30"),
        lambda d: d["reported_fact"].update(religion="not retained"),
        lambda d: d["derived_context"].update(caste="not retained"),
        lambda d: d["reported_fact"].update(menu_context="mixed"),
        lambda d: d["sources"][0].update(phone_number="not retained"),
        lambda d: d.update(record_updated_at="2025-01-01T00:00:00Z"),
        lambda d: d["llm"].update(llm_used=True),
        lambda d: d.update(verification_notes="Contact private@example.org"),
        lambda d: d["review"].update(note="Mobile: 9876543210"),
        lambda d: d["derived_context"].update(derived_context_method="Infer religion from names"),
    ],
)
def test_invalid_record(record, mutation):
    data = record.model_dump(mode="json")
    mutation(data)
    with pytest.raises(ValidationError):
        Event.model_validate(data)
