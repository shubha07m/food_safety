"""Private frozen passages. Existing public extracted-text hashes are unchanged."""

import hashlib
import json
import re
import unicodedata

from bs4 import BeautifulSoup, Comment, NavigableString
from pydantic import BaseModel, ConfigDict, Field

PARSER_VERSION = "passages_v3"


class Passage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    passage_id: str
    original_text: str
    order: int


class DocumentRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    source_id: str
    source_url: str
    source_revision_id: str
    source_language: str
    title: str
    parser_version: str = PARSER_VERSION
    passages: tuple[Passage, ...] = Field(min_length=1)


def freeze_document(html, url, language="und"):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else "Untitled source"
    for element in soup(
        [
            "script",
            "style",
            "nav",
            "footer",
            "header",
            "aside",
            "iframe",
            "form",
            "noscript",
            "svg",
            "button",
            "select",
        ]
    ):
        element.decompose()
    for element in soup.select(
        "[role='navigation'], [aria-label*='breadcrumb' i], "
        "[class*='related' i], [class*='recommend' i], [class*='share' i]"
    ):
        element.decompose()
    content = soup.find("article") or soup.find("main") or soup.body or soup
    # Preserve loose div/span body text too: many publishers do not use <p>.
    # Selecting only paragraph tags can silently omit the actual article body.
    texts, buffer = [], []
    block_names = {
        "p",
        "div",
        "section",
        "article",
        "main",
        "li",
        "ul",
        "ol",
        "blockquote",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "tr",
        "table",
    }

    def flush():
        value = "".join(buffer).strip()
        if value:
            texts.append(value)
        buffer.clear()

    def walk(node):
        if isinstance(node, Comment):
            return
        if isinstance(node, NavigableString):
            buffer.append(str(node))
            return
        if node.name == "br":
            buffer.append("\n")
            return
        block = node.name in block_names
        if block:
            flush()
        for child in node.children:
            walk(child)
        if block:
            flush()

    walk(content)
    flush()
    passages = tuple(
        Passage(passage_id=f"P{i:03d}", original_text=text, order=i)
        for i, text in enumerate((t for t in texts if t), 1)
    )
    if not passages:
        raise ValueError("empty_document")
    payload = json.dumps(
        {"parser": PARSER_VERSION, "passages": [p.original_text for p in passages]},
        ensure_ascii=False,
        sort_keys=True,
    )
    return DocumentRevision(
        source_id="SRC-" + hashlib.sha256(url.encode()).hexdigest()[:20],
        source_url=url,
        source_revision_id=hashlib.sha256(payload.encode()).hexdigest(),
        source_language=language,
        title=title[:600],
        passages=passages,
    )


def mapped_text(text, whitespace=False):
    """NFC view with offsets back to original Unicode code points (not UTF-16)."""
    units = []
    start = 0
    while start < len(text):
        end = start + 1
        while end < len(text) and unicodedata.category(text[end]).startswith("M"):
            end += 1
        units.extend((c, start, end) for c in unicodedata.normalize("NFC", text[start:end]))
        start = end
    if whitespace:
        compact = []
        for char, start, end in units:
            if char.isspace():
                if compact and compact[-1][0] == " ":
                    compact[-1] = (" ", compact[-1][1], end)
                else:
                    compact.append((" ", start, end))
            else:
                compact.append((char, start, end))
        units = compact
    return "".join(c for c, _, _ in units), units


def resolve_quote(text, quote):
    if not quote or len(quote) > 1200:
        raise ValueError("invalid_quote")
    for method in ("exact", "nfc", "whitespace"):
        if method == "exact":
            view, needle = text, quote
            mapping = [(c, i, i + 1) for i, c in enumerate(text)]
        else:
            view, mapping = mapped_text(text, method == "whitespace")
            needle, _ = mapped_text(quote, method == "whitespace")
        matches = list(re.finditer(re.escape(needle), view))
        if len(matches) > 1:
            raise ValueError("ambiguous_repeated_span")
        if matches:
            match = matches[0]
            start, end = mapping[match.start()][1], mapping[match.end() - 1][2]
            if (
                method != "exact"
                and mapped_text(text[start:end], method == "whitespace")[0] != needle
            ):
                raise ValueError("partial_normalized_cluster")
            return {
                "original_quote": text[start:end],
                "start": start,
                "end": end,
                "match_method": method,
            }
    raise ValueError("evidence_not_in_passage")
