from .models import DerivedContext


def contextualize():
    # No inference from names, cuisine or neighbourhood. Explicit review is required.
    return DerivedContext()


def classify_action(text):
    """Classify only explicit action wording; ambiguity stays not reported."""
    value = " ".join(text.casefold().split())
    matches = []
    rules = [
        ("sample collected", ("sample collected", "collected samples", "picked up samples")),
        ("food discarded / destroyed", ("food discarded", "discarded food", "destroyed")),
        ("seizure reported", ("seized", "seizure")),
        ("notice / advisory issued", ("notice issued", "served a notice", "advisory issued")),
        ("lab result reported", ("laboratory result", "lab result")),
        ("inspection / visit only", ("inspected", "inspection", "visited")),
    ]
    for category, phrases in rules:
        if any(phrase in value for phrase in phrases):
            matches.append(category)
    if len(matches) > 1:
        return "multiple actions"
    return matches[0] if matches else "not reported"


def classify_establishment_context(text):
    value = " ".join(text.casefold().split())
    rules = [
        ("mall / food court", ("food court", " mall")),
        ("sweet shop / bakery", ("sweet shop", "bakery")),
        ("market / vendor", (" market", "vendor")),
        ("hotel / hospitality", ("hotel", "hospitality")),
        ("restaurant / eatery", ("restaurant", "eatery", "dhaba")),
    ]
    matches = [
        category for category, phrases in rules if any(phrase in value for phrase in phrases)
    ]
    return matches[0] if len(matches) == 1 else "unknown"


def classify_business_format(text):
    value = " ".join(text.casefold().split())
    if any(phrase in value for phrase in ("part of the chain", "restaurant chain", "group-owned")):
        return "chain_group"
    if any(phrase in value for phrase in ("independently owned", "single-location business")):
        return "independent"
    return "unknown"


def display_summary(facts, context):
    """Create neutral display copy exclusively from validated structured fields."""
    subject = facts.establishment_name
    if not subject and context.establishment_context != "unknown":
        subject = context.establishment_context
    subject = subject or "an unnamed establishment"
    place = f" in {facts.area}" if facts.area else ""
    actions = {
        "inspection / visit only": "an inspection or visit involving",
        "sample collected": "sample collection involving",
        "food discarded / destroyed": "food disposal involving",
        "seizure reported": "a reported seizure involving",
        "notice / advisory issued": "a notice or advisory involving",
        "lab result reported": "a laboratory result involving",
        "multiple actions": "multiple reported actions involving",
        "other": "a source-reported action involving",
        "not reported": "a source-reported food-safety event involving",
    }
    return f"Source reports {actions[context.action_category]} {subject}{place}."
