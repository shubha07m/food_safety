"""Narrow deterministic inspection adapter; no inferred names, actions or findings."""

import re
from datetime import date

from bs4 import BeautifulSoup

from . import __version__
from .classify import display_summary
from .discovery import feed_candidates, page_candidates, relevant_lead
from .models import Event
from .safety import claim_risks

__all__ = ["feed_candidates", "page_candidates", "relevant_lead"]

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
BN_AREAS = "কলকাতা|পার্ক স্ট্রিট|ডেকার্স লেন|সোনারপুর|কামালগাজি|দিঘা|বাদুড়িয়া|বনগাঁ|বকখালি|জয়নগর|জয়নগর|মুচিবাজার|নাগেরবাজার"
BN_PATTERN = re.compile(
    rf"(?P<authority>কলকাতা পুরসভার খাদ্য সুরক্ষা আধিকারিকরা|খাদ্য সুরক্ষা দফতরের আধিকারিকরা) "
    rf"(?P<area>{BN_AREAS})(?:য়|য়|ে| এলাকায়| এলাকায়) "
    r"(?:রেস্তোরাঁ|রেস্তরাঁ|খাবারের দোকান) (?P<action>পরিদর্শন করেছেন|পরিদর্শন করেন)[।.]"
)
BN_VISIT = re.compile(
    rf"(?:শুক্রবার )?(?P<area>{BN_AREAS}) ও সংলগ্ন এলাকার একাধিক জনপ্রিয় রেস্তোরাঁয় "
    r"আচমকা (?P<action>পরিদর্শনে যান) (?P<authority>কলকাতা পুরসভার \(KMC\) স্বাস্থ্য দফতরের আধিকারিকরা)[।.]"
)
BN_SAMPLE = re.compile(
    r"(?P<authority>কলকাতা পুরসভার স্বাস্থ্য দফতরের একটি দল) "
    rf"(?P<area>{BN_AREAS})(?:ের দুই পাশের| এলাকায়| এলাকায়|ে) "
    r"(?:অন্তত )?(?P<quantity>[০-৯]+টি )?(?:দোকান থেকে )?বিভিন্ন খাদ্যসামগ্রীর "
    r"(?P<action>নমুনা সংগ্রহ করে)[।.]"
)
BN_AUTHORITY_OPERATION = re.compile(
    r"(?:বনগাঁ মহকুমা শাসকের উপস্থিতিতে এবার )?"
    r"(?P<authority>খাদ্য সুরক্ষা দপ্তর|খাদ্য সুরক্ষা দফতর)(?:ের)? "
    rf"(?P<action>অভিযান) (?P<area>{BN_AREAS})(?:র| এলাকায়| এলাকায়) "
    r"(?:বিভিন্ন |একাধিক )?(?:হোটেল, রেস্তোরাঁয়|হোটেল, রেস্তরাঁয়|দোকানে)[।.]"
)
BN_KOLKATA_OPERATION = re.compile(
    r"(?P<area>কলকাতা): (?:রবিবার সকালে )?(?:শহর কলকাতার )?"
    r"(?:একের পর এক |একাধিক )?রেস্তোরাঁয় (?P<action>অভিযান চালাচ্ছে) "
    r"(?P<authority>খাদ্য সুরক্ষা দফতর)[।.]"
)
EN_AGGREGATE = re.compile(
    rf"(?P<authority>{AUTHORITY}) (?P<action>inspected|visited) "
    r"(?P<quantity>[0-9][0-9,]* (?:establishments|restaurants|eateries|food shops)) "
    rf"(?:across|in) (?P<area>{'|'.join(AREAS)}|West Bengal)(?:, India)?\.",
    re.I,
)
EN_NAMED = re.compile(
    rf"(?P<authority>{AUTHORITY}) (?P<action>inspected|visited) "
    r"(?P<names>[A-Z][A-Za-z0-9’'&. -]{1,45}(?: and [A-Z][A-Za-z0-9’'&. -]{1,45})?) "
    rf"in (?P<area>{'|'.join(AREAS)})(?:, (?:Kolkata|West Bengal))?\.",
    re.I,
)
BLOCKED = re.compile(
    r"\b(?:not|never|denied|alleged|reportedly|may|might|would|will|planned|"
    r"correction|corrected|withdrawn|retracted|clarification|disputed)\b",
    re.I,
)


def supported_fields(sentence):
    match = (
        PATTERN.fullmatch(sentence)
        or BN_PATTERN.fullmatch(sentence)
        or BN_VISIT.fullmatch(sentence)
        or BN_SAMPLE.fullmatch(sentence)
        or BN_AUTHORITY_OPERATION.fullmatch(sentence)
        or BN_KOLKATA_OPERATION.fullmatch(sentence)
        or EN_AGGREGATE.fullmatch(sentence)
    )
    if not match:
        return None
    fields = {
        "reported_observation": sentence,
        "reported_action": match["action"],
        "reported_authority": match["authority"],
        "area": match["area"],
    }
    if "quantity" in match.groupdict() and match["quantity"]:
        fields["reported_quantity"] = match["quantity"].strip()
    return fields


def automatic_matches(text):
    """Return distinct exact supported spans; never infer entities or expand aggregates."""
    result = []
    for named in EN_NAMED.finditer(text):
        sentence = named.group(0)
        names = re.split(r"\s+and\s+", named["names"], flags=re.I) if named else []
        generic = {"restaurants", "eateries", "food stalls", "food shops", "markets"}
        if named and all(name.casefold() not in generic for name in names):
            for name in names:
                fields = {
                    "reported_observation": sentence,
                    "reported_action": named["action"],
                    "reported_authority": named["authority"],
                    "area": named["area"],
                    "establishment_name": name,
                }
                result.append((sentence, fields, "establishment_event"))
    seen = {row[0] for row in result}
    for pattern in [
        PATTERN,
        BN_PATTERN,
        BN_VISIT,
        BN_SAMPLE,
        BN_AUTHORITY_OPERATION,
        BN_KOLKATA_OPERATION,
        EN_AGGREGATE,
    ]:
        for match in pattern.finditer(text):
            sentence = match.group(0)
            if sentence in seen:
                continue
            fields = supported_fields(sentence)
            scope = "statewide_operation" if fields["area"] == "West Bengal" else "area_operation"
            result.append((sentence, fields, scope))
            seen.add(sentence)
    return result


def prepare_automatic(event, html, text, at, selected=None):
    """Return an eligible record or None; never set a human-review attestation."""
    selected_text = selected[0] if selected else text
    position = text.find(selected_text)
    context = text[max(0, position - 160) : position + len(selected_text) + 200]
    if BLOCKED.search(context) or claim_risks(selected_text) or event.llm.llm_used:
        return None
    if re.search("অস্বীকার|সংশোধনী|প্রত্যাহার|ঘটেনি", text):
        return None
    matches = automatic_matches(text)
    if selected is None and len(matches) == 1:
        selected = matches[0]
    if selected is None or selected not in matches:
        return None
    soup = BeautifulSoup(html, "html.parser")
    meta = soup.find(
        "meta",
        attrs={"property": re.compile(r"^(?:article:published_time|datePublished)$", re.I)},
    ) or soup.find(
        "meta", attrs={"name": re.compile(r"^(?:article:published_time|datePublished)$", re.I)}
    )
    raw = meta.get("content", "") if meta else ""
    if not raw:
        structured = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2}(?:T[^"]*)?)"', html)
        raw = structured.group(1) if structured else ""
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T.*)?", raw):
        return None
    try:
        published = date.fromisoformat(raw[:10])
    except ValueError:
        return None
    if published > at.date():
        return None
    sentence, fields, scope = selected
    data = event.model_dump(mode="json")
    url = data["sources"][0]["source_url"]
    data["reported_fact"] = {
        **fields,
        "evidence": {key: {"source_url": url, "quote": sentence} for key in fields},
    }
    data["sources"][0].update(
        source_date=published.isoformat(),
        evidence_quote=sentence,
        evidence_context=sentence,
        evidence_span_hash="",
    )
    data["verification_status"] = "SOURCE VERIFIED"
    data.update(
        publication_status="active",
        evidence_support_status="supported_as_of",
        source_availability="available",
        first_published_at=at.isoformat(),
        last_successful_evidence_check_at=at.isoformat(),
        last_source_checked_at=at.isoformat(),
        extractor_id="explicit_inspection_sentence",
        extractor_version="2",
        record_scope=scope,
    )
    data["verification_notes"] = (
        "Automatic exact-source inspection adapter; no human review is claimed. "
        "Publication date is used; event date is not established."
    )
    data["automatic_validation"] = {
        "method": "explicit_inspection_sentence_v2",
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
    if event.llm.llm_used:
        from .documents import mapped_text
        from .models import DerivedContext

        proof = (
            event.automatic_validation.extraction_evidence if event.automatic_validation else None
        )
        if (
            not event.automatic_validation
            or event.automatic_validation.method != "source_grounded_candidate_v1"
            or not proof
            or not event.llm.llm_output_was_validated
            or event.llm.validation_result != "passed"
            or event.llm.source_revision_id != proof.source_revision_id
            or proof.end - proof.start != len(proof.original_quote)
            or mapped_text(proof.original_quote, True)[0]
            != mapped_text(event.reported_fact.reported_observation, True)[0]
            or len(event.sources) != 1
        ):
            return ["invalid_llm_grounding_provenance"]
        if event.derived_context != DerivedContext() or not event.sources[0].source_date:
            return ["automatic_context_or_date_invalid"]
        if event.sources[0].source_date > event.automatic_validation.validated_at.date():
            return ["automatic_future_date"]
        return []

    proposals = automatic_matches(event.reported_fact.reported_observation)
    facts = event.reported_fact.model_dump(exclude={"evidence"})
    fields = next(
        (
            fields
            for _, fields, scope in proposals
            if all(facts.get(key) == value for key, value in fields.items())
        ),
        None,
    )
    if not fields or not event.automatic_validation or len(event.sources) != 1:
        return ["invalid_automatic_provenance"]
    if any(facts[key] != value for key, value in fields.items()):
        return ["automatic_field_mismatch"]
    if any(
        value is not None
        for key, value in facts.items()
        if key not in fields and key != "legal_finding_status"
    ):
        return ["automatic_extra_claim"]
    if facts["legal_finding_status"] != "unknown":
        return ["automatic_extra_claim"]
    if event.automatic_validation.method == "source_grounded_candidate_v1":
        return ["missing_llm_provenance"]
    from .models import DerivedContext

    if event.derived_context != DerivedContext() or not event.sources[0].source_date:
        return ["automatic_context_or_date_invalid"]
    if event.sources[0].source_date > event.automatic_validation.validated_at.date():
        return ["automatic_future_date"]
    return []


# Backwards-compatible imports above keep the public adapter API stable.
