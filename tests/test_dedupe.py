from conftest import AT

from food_safety.dedupe import associate, same_event, stable_id


def test_stable_id():
    assert stable_id("https://example.org/a", " An Inspection ") == stable_id(
        "https://example.org/a", "an inspection"
    )


def test_secondary_source_retained(record):
    second = record.model_copy(deep=True)
    object.__setattr__(second.sources[0], "source_id", "")
    second.sources[0].source_url = "https://example.net/fixture"
    second.sources[0].source_publisher = "Second synthetic publisher"
    merged = associate(record, second, AT)
    assert len(merged.sources) == 2
    assert merged.event_id == record.event_id
    assert merged.review is None
    assert merged.verification_status == "PENDING REVIEW"


def test_different_establishments_not_merged(record):
    other = record.model_copy(deep=True)
    other.reported_fact.establishment_name = "Another synthetic fixture"
    assert not same_event(record, other)


def test_unnamed_events_not_merged(record):
    other = record.model_copy(deep=True)
    other.event_id = "WBFS-aaaaaaaaaaaa"
    other.reported_fact.establishment_name = None
    assert not same_event(record, other)


def test_conflicting_quantities_not_merged(record):
    other = record.model_copy(deep=True)
    other.reported_fact.reported_quantity = "5 kg"
    assert not same_event(record, other)
