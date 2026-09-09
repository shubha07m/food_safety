import hashlib
import re

from bs4 import BeautifulSoup

from .safety import claim_risks


def article_text(html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled source"
    for element in soup(["script", "style", "nav", "footer", "header", "iframe", "form"]):
        element.decompose()
    content = soup.find("article") or soup.find("main") or soup.body or soup
    text = " ".join(content.get_text(" ", strip=True).split())
    if not text:
        raise ValueError("empty_article")
    return title[:600], text


def text_hash(text):
    return hashlib.sha256(text.encode()).hexdigest()


def deterministic_extract(text):
    """Generate an unnamed candidate only; never guess date, location or establishments."""
    if claim_risks(text):
        raise ValueError("suspicious_or_sensitive_content")
    if re.search(r"\b(corrected|correction|withdrawn|retracted|clarification)\b", text, re.I):
        raise ValueError("source_update_requires_review")
    for sentence in re.split(r"(?<=[.!?।])\s+", text):
        if 3 <= len(sentence.split()) <= 25 and re.search(
            r"\b(inspect\w*|samples? collected|collected samples?|seized|notice issued)\b"
            r"|পরিদর্শন|অভিযান|নমুনা সংগ্রহ",
            sentence,
            re.I,
        ):
            return {"reported_observation": sentence}
    raise ValueError("no_bounded_evidence_span")
