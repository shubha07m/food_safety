"""Narrow deterministic inspection adapter; no inferred names, actions or findings."""

import re
from datetime import date
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from . import __version__
from .classify import display_summary
from .models import Event
from .safety import claim_risks

# Only explicit inspection statements with an authority, object and WB locality.
# Deliberately excludes allegations, quantities, notices, plans and legal findings.
AREAS = (
    "Park Street",
    "Dacres Lane",
    "Lake Market",
    "Gariahat",
    "Bowbazar",
    "Tangra",
    "Jorabagan",
    "Sonarpur",
    "Kamalgazi",
    "Dum Dum",
    "Digha",
    "Baduria",
    "Kolkata",
)
AUTHORITY = r"(?:KMC|Kolkata Municipal Corporation) food safety (?:officials|teams|inspectors)"
PATTERN = re.compile(
    rf"(?P<authority>{AUTHORITY}) (?P<action>inspected|visited) "
    rf"(?:restaurants|eateries|food stalls|food shops|markets) in "
    rf"(?P<area>{'|'.join(AREAS)})(?:, (?:Kolkata|West Bengal))?\.",
    re.I,
)
BLOCKED = re.compile(
    r"\b(?:not|never|denied|alleged|reportedly|may|might|would|will|planned|"
    r"correction|corrected|withdrawn|retracted|clarification|disputed)\b",
    re.I,
)


def supported_fields(sentence):
    match = PATTERN.fullmatch(sentence)
    if not match:
        return None
    return {
        "reported_observation": sentence,
        "reported_action": match["action"],
        "reported_authority": match["authority"],
        "area": match["area"],
    }


def prepare_automatic(event, html, text, at):
    """Return an eligible record or None; never set a human-review attestation."""
    if BLOCKED.search(text) or claim_risks(text) or event.llm.llm_used:
        return None
    matches = [s for s in re.split(r"(?<=[.!?])\s+", text) if supported_fields(s)]
    if len(matches) != 1:
        return None
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    raw = meta.get("content", "") if meta else ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", raw):
        return None
    try:
        published = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    if published > at.date():
        return None
    fields = supported_fields(matches[0])
    data = event.model_dump(mode="json")
    url = data["sources"][0]["source_url"]
    data["reported_fact"] = {
        **fields,
        "evidence": {key: {"source_url": url, "quote": matches[0]} for key in fields},
    }
    data["sources"][0].update(
        source_date=published.isoformat(),
        evidence_quote=matches[0],
        evidence_context=matches[0],
    )
    data["verification_status"] = "SOURCE VERIFIED"
    data["verification_notes"] = (
        "Automatic exact-source inspection adapter; no human review is claimed. "
        "Publication date is used; event date is not established."
    )
    data["automatic_validation"] = {
        "method": "explicit_inspection_sentence_v1",
        "validated_at": at.isoformat(),
        "pipeline_version": __version__,
    }
    data["history"][-1].update(
        status="SOURCE VERIFIED",
        note="Deterministic inspection and source validation passed.",
    )
    draft = Event.model_validate(data)
    data["display_summary"] = display_summary(draft.reported_fact, draft.derived_context)
    return Event.model_validate(data)


def automatic_errors(event):
    fields = supported_fields(event.reported_fact.reported_observation)
    if not fields or not event.automatic_validation or len(event.sources) != 1:
        return ["invalid_automatic_provenance"]
    facts = event.reported_fact.model_dump(exclude={"evidence"})
    if any(facts[key] != value for key, value in fields.items()):
        return ["automatic_field_mismatch"]
    if any(
        value is not None
        for key, value in facts.items()
        if key not in fields and key != "legal_finding_status"
    ):
        return ["automatic_extra_claim"]
    if facts["legal_finding_status"] != "unknown" or event.llm.llm_used:
        return ["automatic_extra_claim"]
    from .models import DerivedContext

    if event.derived_context != DerivedContext() or not event.sources[0].source_date:
        return ["automatic_context_or_date_invalid"]
    if event.sources[0].source_date > event.automatic_validation.validated_at.date():
        return ["automatic_future_date"]
    return []


def feed_candidates(body, policy, limit):
    """RSS/Atom discovery leads; snippets never become publication evidence."""
    from xml.etree import ElementTree

    from .safety import safe_url

    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", body, re.I):
        raise ValueError("feed_declarations_not_allowed")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid_feed") from exc
    result = []
    for item in list(root.iter())[:1000]:
        if item.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        text = " ".join(item.itertext())
        if not re.search(r"food.{0,30}(safety|inspect)|খাদ্য.{0,20}(সুরক্ষা|নিরাপত্তা)", text, re.I):
            continue
        for child in item:
            if child.tag.rsplit("}", 1)[-1] != "link":
                continue
            try:
                url = safe_url(child.get("href") or child.text or "")
            except ValueError:
                continue
            if urlsplit(url).hostname == policy.domain and url not in result:
                result.append(url)
        if len(result) >= limit:
            break
    return result[:limit]


def page_candidates(body, policy, limit):
    """One configured index page, exact same-domain links; no recursive crawling."""
    from urllib.parse import urljoin

    from .safety import safe_url

    result = []
    for anchor in BeautifulSoup(body, "html.parser").find_all("a", href=True)[:1000]:
        label = anchor.get_text(" ", strip=True) + " " + anchor["href"]
        if not re.search(r"food[-\s].{0,35}(safety|inspect)|খাদ্য.{0,20}(সুরক্ষা|নিরাপত্তা)", label, re.I):
            continue
        try:
            url = safe_url(urljoin(f"https://{policy.domain}/", anchor["href"]))
        except ValueError:
            continue
        if urlsplit(url).hostname == policy.domain and url not in result:
            result.append(url)
        if len(result) >= limit:
            break
    return result
