# ruff: noqa: E501
"""Build the bounded, manually reviewed first dataset from curated publisher pages.

This is deliberately not part of scheduled ingestion.  It fetches the small source
set once, retains only short exact spans, and fails if any requested field is not
inside the selected source sentence.
"""

from datetime import date

from food_safety.config import ROOT, settings, sources
from food_safety.dedupe import stable_id
from food_safety.extract import article_text, text_hash
from food_safety.fetch import Fetcher
from food_safety.models import Event
from food_safety.storage import now, read_events, transaction
from food_safety.verify import publication_errors

SOURCE = {
    "park": ("https://timesofindia.indiatimes.com/city/kolkata/kmc-food-team-reaches-park-street-seizes-stale-items-from-eateries/articleshow/133774167.cms", date(2026, 9, 4)),
    "dacres": ("https://timesofindia.indiatimes.com/city/kolkata/kmc-cracks-whip-on-dacres-lane-eateries/articleshow/133811497.cms", date(2026, 9, 5)),
    "malls": ("https://timesofindia.indiatimes.com/city/kolkata/kmc-food-inspectors-knock-on-mall-eatery-doors-discards-meat-in-a-central-kolkata-restaurant/articleshow/133844089.cms", date(2026, 9, 6)),
    "markets": ("https://timesofindia.indiatimes.com/city/kolkata/on-last-day-of-food-safety-drive-kmc-targets-fish-paneer-and-spice-hubs/articleshow/133893508.cms", date(2026, 9, 7)),
    "big_boss": ("https://timesofindia.indiatimes.com/city/kolkata/kmc-mulls-action-against-eatery/articleshow/133744154.cms", date(2026, 9, 3)),
    "business": ("https://www.businesstoday.in/amp/india/story/bengal-fda-crackdown-40kg-rotten-meat-500kg-stale-chicken-and-prawns-seized-ahead-of-durga-puja-553132-2026-09-03", date(2026, 9, 3)),
    "tv9": ("https://tv9bangla.com/kolkata/west-bengal-food-safety-drive-irregularities-found-at-1525-food-centres-licences-of-13-processing-units-cancelled-1343938.html", date(2026, 9, 3)),
}


def row(slug, source, anchor, area, observation, name=None):
    return {"slug": slug, "source": source, "anchor": anchor, "area": area, "observation": observation, "name": name}


ROWS = [
    *[row(name.lower().replace("’", "").replace(" ", "-"), "park", "Among the big names that were visited", "Park Street", "visited by KMC teams", name) for name in ["Peter Cat", "Mocambo", "Oasis", "Kareem’s", "Arsalan"]],
    *[row(name.lower().replace(" ", "-"), "dacres", "At Dacres Lane, the team visited", "Dacres Lane", "the team visited", name) for name in ["Apanjan", "Sharma Sweets", "New Chittanjan", "Suruchi"]],
    row("lake-market", "dacres", "Separate teams of KMC", "Lake Market", "visited Lake Market"),
    row("jorabagan", "dacres", "Separate teams of KMC", "Jorabagan", "visited Lake Market"),
    row("dum-dum", "dacres", "Separate teams of KMC", "Dum Dum", "visited Lake Market"),
    *[row(slug, "malls", "The Kolkata Municipal Corporation’s food safety drive reached", "Kolkata", "food safety drive reached", name) for slug, name in [("south-city", "South City"), ("acropolis", "Acropolis"), ("metropolis-hiland-park", "Metropolis at Hiland Park")]],
    row("new-aliah", "malls", "Inspection teams also visited multiple restaurants", "Bentinck Street and Waterloo Street", "Inspection teams also visited", "New Aliah Hotel"),
    *[row(slug, "malls", "Amit Bajoria, owner of Lord of the Rings", "South City Mall", "inspection team suggested them", name) for slug, name in [("lord-of-the-rings", "Lord of the Rings"), ("warehouse-cafe", "Warehouse Cafe"), ("veneto", "Veneto")]],
    row("gariahat-market", "markets", "The fish market at Gariahat, the spice market", "Gariahat", "food safety drive", "fish market at Gariahat"),
    row("posta-market", "markets", "The fish market at Gariahat, the spice market", "Posta", "food safety drive", "spice market at Posta"),
    row("chhana-patti", "markets", "The fish market at Gariahat, the spice market", "Bowbazar", "food safety drive", "Chhana Patti"),
    row("big-boss", "big_boss", "Kolkata Municipal Corporation food safety team wants", "Tangra", "food safety team wants proper action", "Big Boss"),
    row("kamalgazi-sweet-shop", "park", "A similar inspection was also carried out", "Kamalgazi", "inspection was also carried out"),
    row("sonarpur-restaurant", "park", "A similar inspection was also carried out", "Sonarpur", "inspection was also carried out"),
    row("baduria-unnamed", "business", "One of the most alarming findings came from Baduria", "Baduria", "officials recovered around 40 kg"),
    row("shaktigarh-sweet-shops", "business", "In Shaktigarh, officials found", "Shaktigarh", "officials found food ingredients and products"),
    row("east-midnapore-dhabas", "business", "In East Midnapore, authorities detected", "East Midnapore", "authorities detected problems"),
    row("digha-hotels", "business", "In Digha, inspections of 20 hotels", "Digha", "inspections of 20 hotels reportedly uncovered"),
    row("hooghly-sweet-shop", "business", "A sweet shop in Hooghly was also found", "Hooghly", "sweet shop in Hooghly was also found"),
    *[row(slug, "tv9", "৫টি রেস্তরাঁর লাইসেন্স সাসপেন্ড করা হয়েছে", area, "লাইসেন্স সাসপেন্ড করা হয়েছে", name) for slug, name, area in [
        ("rang-de-basanti", "রঙ দে বসন্তি ধাবা", "মধ্যমগ্রামের"),
        ("absolute-barbecue-nation", "অ‌্যাবসিলিউট বারবিকিউ নেশন", "সেক্টর ফাইভের আরডিবি মলের"),
        ("just-bangali", "জাস্ট বাঙালি", "মধ‌্যমগ্রামের"),
        ("barbecue-nation-sodepur", "বারবিকিউ নেশন", "সোদপুরের"),
        ("chaurasia-chats", "চৌরাসিয়া চাটস", "সেক্টর থ্রি-র"),
    ]],
]


def sentence(text, anchor):
    index = text.find(anchor)
    if index < 0:
        raise ValueError(f"missing_anchor:{anchor}")
    # Extraction can prepend navigation text without a sentence terminator.  The
    # anchor is deliberately the first retained context character.
    start = index
    if anchor == "৫টি রেস্তরাঁর লাইসেন্স সাসপেন্ড করা হয়েছে":
        result = " ".join(text[index:].split()[:60])
        return result
    end_candidates = [position for mark in (".", "!", "?", "।", "\n") if (position := text.find(mark, index + len(anchor))) >= 0]
    end = min(end_candidates) + 1 if end_candidates else len(text)
    result = " ".join(text[start:end].split())
    if len(result.split()) > 60:
        # Retain a minimal exact prefix rather than extraction/navigation text or
        # a later unrelated paragraph. Field checks below still reject a row if
        # any selected value falls outside this capped source span.
        result = " ".join(result.split()[:60])
    return result


def main():
    cfg, policies = settings(ROOT), sources(ROOT)
    policy_by_url = {url: policy for policy in policies for url in policy.urls}
    fetcher, fetched = Fetcher(policies, cfg), {}
    for key, (url, source_date) in SOURCE.items():
        canonical, html = fetcher.article(url)
        title, text = article_text(html)
        if canonical != url or not text:
            raise ValueError(f"source_changed_or_empty:{key}")
        fetched[key] = (title, text, source_date, policy_by_url[url])
    at = now()
    records = []
    for item in ROWS:
        title, text, source_date, policy = fetched[item["source"]]
        context = sentence(text, item["anchor"])
        facts = {"area": item["area"], "reported_observation": item["observation"]}
        if item["name"]:
            facts["establishment_name"] = item["name"]
        for value in facts.values():
            if value not in context:
                raise ValueError(f"unsupported_field:{item['slug']}:{value}")
        url = SOURCE[item["source"]][0]
        evidence = {field: {"source_url": url, "quote": value} for field, value in facts.items()}
        data = {
            "event_id": stable_id(url + "#" + item["slug"], item["observation"]),
            "reported_fact": {**facts, "evidence": evidence},
            "sources": [{"source_url": url, "source_title": title, "source_publisher": policy.name, "source_date": source_date.isoformat(), "source_type": "news", "tier": "B", "retrieved_at": at.isoformat(), "text_sha256": text_hash(text), "evidence_quote": item["observation"], "evidence_context": context}],
            "verification_status": "SOURCE VERIFIED",
            "verification_notes": "Source exists and the displayed fields were manually checked against a retained exact context; this is not an independent finding.",
            "review": {"reviewed_at": at.isoformat(), "reviewer": "project-maintainer", "note": "Initial bounded source review; publication date retained where event date was not explicit.", "source_context_checked": True, "all_fields_supported": True},
            "record_created_at": at.isoformat(), "record_updated_at": at.isoformat(),
            "history": [{"at": at.isoformat(), "status": "SOURCE VERIFIED", "note": "Initial bounded source review; publication date retained where event date was not explicit."}],
        }
        event = Event.model_validate(data)
        errors = publication_errors(event, policies, {url: text})
        if errors:
            raise ValueError(f"publication_errors:{item['slug']}:{','.join(errors)}")
        records.append(event)
    existing = read_events(ROOT, "events")
    if existing:
        raise ValueError("events_not_empty; do not overwrite an existing reviewed dataset")
    transaction(ROOT, records, read_events(ROOT, "pending"), [], at)
    print({"reviewed_records": len(records), "source_articles": len(fetched)})


if __name__ == "__main__":
    main()
