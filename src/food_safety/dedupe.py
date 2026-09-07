import hashlib

from .safety import normalize


def stable_id(url, observation):
    value = f"{url}|{normalize(observation)}"
    return "WBFS-" + hashlib.sha256(value.encode()).hexdigest()[:12]


def same_event(left, right):
    a, b = left.reported_fact, right.reported_fact
    # Unnamed/undated records are never fuzzy-merged across different publishers.
    if not all(
        [a.event_date, b.event_date, a.area, b.area, a.establishment_name, b.establishment_name]
    ):
        return left.event_id == right.event_id
    return (
        a.event_date == b.event_date
        and normalize(a.area) == normalize(b.area)
        and normalize(a.establishment_name) == normalize(b.establishment_name)
        and normalize(a.reported_observation) == normalize(b.reported_observation)
        and a.reported_action == b.reported_action
        and a.reported_quantity == b.reported_quantity
    )


def associate(left, right, at):
    """Retain the first ID and every distinct source; re-review associated claims."""
    if not same_event(left, right):
        raise ValueError("not_same_event")
    data = left.model_dump(mode="json")
    by_url = {s.source_url: s.model_dump(mode="json") for s in left.sources}
    for source in right.sources:
        if source.source_url in by_url and by_url[source.source_url] != source.model_dump(
            mode="json"
        ):
            raise ValueError("source_revision_requires_review")
        by_url[source.source_url] = source.model_dump(mode="json")
    data.update(
        sources=list(by_url.values()),
        review=None,
        verification_status="PENDING REVIEW",
        record_updated_at=at.isoformat(),
        verification_notes="Sources associated; re-review.",
    )
    data["history"].append(
        {
            "at": at.isoformat(),
            "status": "PENDING REVIEW",
            "note": "Additional source associated; provenance retained.",
        }
    )
    return type(left).model_validate(data)
