"""One-time reviewed V2 migration for the initial 35-record evaluation dataset."""

import hashlib
import json

from food_safety import SCHEMA_VERSION, __version__
from food_safety.classify import display_summary
from food_safety.config import ROOT
from food_safety.models import Event
from food_safety.storage import dump, now, transaction

TOI_PARK = "kmc-food-team-reaches-park-street"
TOI_DACRES = "kmc-cracks-whip-on-dacres-lane"
TOI_MALLS = "kmc-food-inspectors-knock-on-mall"
TOI_MARKETS = "on-last-day-of-food-safety-drive"
TOI_BIG_BOSS = "kmc-mulls-action-against-eatery"
BUSINESS_TODAY = "businesstoday.in"
TV9 = "tv9bangla.com"


def reviewed_context(event):
    source = event.sources[0]
    url = source.source_url
    name = event.reported_fact.establishment_name
    area = event.reported_fact.area
    action = "not reported"
    establishment = "unknown"

    if any(token in url for token in (TOI_PARK, TOI_DACRES, TOI_MALLS, TOI_MARKETS)):
        action = "inspection / visit only"
    elif TOI_BIG_BOSS in url or TV9 in url:
        action = "other"
    elif BUSINESS_TODAY in url:
        if area == "Digha":
            action = "inspection / visit only"
        elif area == "Baduria":
            action = "other"

    if TOI_PARK in url:
        if area == "Kamalgazi":
            establishment = "sweet shop / bakery"
        else:
            establishment = "restaurant / eatery"
    elif TOI_DACRES in url and name:
        establishment = "restaurant / eatery"
    elif TOI_MALLS in url:
        establishment = (
            "hotel / hospitality" if name == "New Aliah Hotel" else "mall / food court"
        )
    elif TOI_MARKETS in url:
        establishment = "market / vendor"
    elif TOI_BIG_BOSS in url or TV9 in url:
        establishment = "restaurant / eatery"
    elif BUSINESS_TODAY in url:
        establishment = {
            "Baduria": "restaurant / eatery",
            "Shaktigarh": "sweet shop / bakery",
            "East Midnapore": "restaurant / eatery",
            "Digha": "hotel / hospitality",
            "Hooghly": "sweet shop / bakery",
        }[area]

    normalized = {
        "মধ্যমগ্রামের": "Madhyamgram",
        "মধ‌্যমগ্রামের": "Madhyamgram",
        "সেক্টর ফাইভের আরডিবি মলের": "Sector V",
        "সোদপুরের": "Sodepur",
        "সেক্টর থ্রি-র": "Sector III",
    }.get(area, area)
    data = {
        "normalized_area": normalized,
        "derived_context_sources": [url],
        "derived_context_method": (
            "Maintainer-reviewed normalization and categories based only on explicit "
            "publisher wording retained with this record."
        ),
        "derived_confidence": "high",
    }
    if action != "not reported":
        data.update(
            action_category=action,
            action_category_source=url,
            action_category_method="reviewed_source_context",
            action_category_confidence="high",
            action_category_reviewed=True,
        )
    if establishment != "unknown":
        data.update(
            establishment_context=establishment,
            establishment_context_source=url,
            establishment_context_method="publisher_explicit",
            establishment_context_confidence="high",
            establishment_context_reviewed=True,
        )
    return data


def enrich_facts(event, facts):
    source = event.sources[0]
    context = source.evidence_context
    url = source.source_url
    observation = facts["reported_observation"]
    action_phrases = {
        "visited by KMC teams",
        "the team visited",
        "Inspection teams also visited",
        "inspection was also carried out",
        "inspections of 20 hotels reportedly uncovered",
        "officials recovered around 40 kg",
        "লাইসেন্স সাসপেন্ড করা হয়েছে",
    }
    if observation in action_phrases or (
        event.reported_fact.area == "Lake Market" and observation == "visited Lake Market"
    ):
        facts["reported_action"] = observation
        facts["evidence"]["reported_action"] = {"source_url": url, "quote": observation}
    if "around 40 kg" in observation:
        facts["reported_quantity"] = "around 40 kg"
        facts["evidence"]["reported_quantity"] = {
            "source_url": url,
            "quote": "around 40 kg",
        }
    authority = None
    if "Kolkata Municipal Corporation" in context:
        authority = "Kolkata Municipal Corporation"
    elif "KMC" in context:
        authority = "KMC"
    if authority:
        facts["reported_authority"] = authority
        facts["evidence"]["reported_authority"] = {"source_url": url, "quote": authority}


def main():
    raw_events = json.loads((ROOT / "data/events.json").read_text())["records"]
    if len(raw_events) != 35:
        raise ValueError("migration_requires_initial_35_record_dataset")
    raw_pending = json.loads((ROOT / "data/pending.json").read_text())["records"]
    raw_rejected = json.loads((ROOT / "data/rejected.json").read_text())["records"]
    at = now()
    enriched = []
    for raw in raw_events:
        previous_digest = hashlib.sha256(
            json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        dump(ROOT / "data/history" / raw["event_id"] / f"{previous_digest}.json", raw)
        model_input = {**raw, "derived_context": {}, "display_summary": None}
        old = Event.model_validate(model_input)
        data = old.model_dump(mode="json")
        data["record_updated_at"] = at.isoformat()
        data["history"] = [
            *raw["history"],
            {
                "at": at.isoformat(),
                "status": raw["verification_status"],
                "note": (
                    "V0.2 reviewed contextual enrichment; reported facts remain source-linked."
                ),
                "previous_record_sha256": previous_digest,
            },
        ]
        enrich_facts(old, data["reported_fact"])
        data["derived_context"] = reviewed_context(old)
        draft = Event.model_validate(data)
        data["display_summary"] = display_summary(draft.reported_fact, draft.derived_context)
        data["pipeline_version"] = __version__
        enriched.append(Event.model_validate(data))
    pending = [Event.model_validate(record) for record in raw_pending]
    transaction(ROOT, enriched, pending, raw_rejected, at)
    dump(
        ROOT / "data/schema_version.json",
        {"schema_version": SCHEMA_VERSION, "pipeline_version": __version__},
    )
    print({"records": len(enriched), "pipeline_version": __version__})


if __name__ == "__main__":
    main()
