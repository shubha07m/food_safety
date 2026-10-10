"""Deterministic JSON-LD Event extraction before optional model use, never publication."""

import html
import json
import re

from bs4 import BeautifulSoup

from ..documents import freeze_document
from .models import Candidate, Extraction, SupportedValue


def events(html_text, url, language, *, profile=False):
    soup = BeautifulSoup(html_text, "html.parser")
    entries = []
    for script in soup.select('script[type="application/ld+json"]')[:20]:
        raw = script.string or script.get_text()
        if len(raw) > 64000:
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        values = value if isinstance(value, list) else [value]
        if isinstance(value, dict) and isinstance(value.get("@graph"), list):
            values = value["@graph"]
        for event in values[:50]:
            if not isinstance(event, dict):
                continue
            kind = event.get("@type", "")
            if "Event" not in (kind if isinstance(kind, list) else [kind]):
                continue
            name = event.get("name")
            location = event.get("location")
            if not isinstance(name, str) or not re.search(r"puja|pujo|durgotsav", name, re.I):
                continue
            location = location if isinstance(location, dict) else {}
            # Dates do not confer a geographic anchor. Preserve the legacy
            # structured address contract; do not parse a string into a city.
            address = location.get("address")
            address = address if isinstance(address, dict) else {}
            city = address.get("addressLocality")
            location_usable = isinstance(city, str) and bool(city.strip())
            if not profile and not location_usable:
                continue
            fields = {
                "name": name,
                "area": city,
                "city": city,
                "venue": location.get("name"),
                "address": address.get("streetAddress"),
                "event_dates": event.get("startDate"),
                "end_date": event.get("endDate"),
            }
            if profile:
                fields = {
                    "name": name,
                    "locality": city,
                    "venue": location.get("name") if location_usable else None,
                    "address": address.get("streetAddress") if location_usable else None,
                    "start_date": event.get("startDate"),
                    "end_date": event.get("endDate"),
                }
                start = event.get("startDate")
                if isinstance(start, str) and re.match(r"^\d{4}-", start):
                    fields["year"] = start[:4]
            organizer = event.get("organizer")
            if isinstance(organizer, dict):
                fields["organizer"] = organizer.get("name")
            # Exact raw script is kept privately as evidence. Unsupported escaped
            # values fall through to operator review rather than invented quotes.
            fields = {
                k: v
                for k, v in fields.items()
                if isinstance(v, str) and 0 < len(v) <= 300 and v in raw
            }
            required = ("name",) if profile else ("name", "area", "city")
            if all(k in fields for k in required):
                entries.append((raw, fields))
    if not entries:
        return None
    entries = entries[:30]
    document = freeze_document(
        "<title>Source JSON-LD events</title><main>"
        + "".join(f"<p>{html.escape(raw)}</p>" for raw, _ in entries)
        + "</main>",
        url,
        language,
    )
    candidates = []
    for _, fields in entries:
        supported = {}
        for key, value in fields.items():
            passage = next((p for p in document.passages if value in p.original_text), None)
            if passage:
                supported[key] = SupportedValue(
                    raw_value=value, passage_id=passage.passage_id, original_quote=value
                )
        if profile:
            from .leads import Lead

            candidates.append(Lead(**supported))
        elif all(k in supported for k in ("name", "area", "city")):
            candidates.append(Candidate(candidate_id=f"C{len(candidates) + 1}", **supported))
    if profile:
        from .leads import LeadOutput

        return document, LeadOutput(completion_status="complete", candidates=candidates[:20])
    return document, Extraction(completion_status="complete", candidates=candidates)
