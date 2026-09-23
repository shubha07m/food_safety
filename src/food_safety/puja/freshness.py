"""Small source receipts, not publication decisions or scheduled extraction."""

import hashlib
import html as html_escape
import json
import time
import unicodedata
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from ..config import SourcePolicy
from ..config import settings as pipeline_settings
from ..documents import freeze_document
from ..storage import dump
from .pipeline import PujaFetcher, load_config


class NotModified(Exception):
    pass


def header(value):
    return (
        value
        if isinstance(value, str)
        and len(value) <= 512
        and not any(ord(c) < 32 or ord(c) > 126 for c in value)
        else None
    )


class MonitorFetcher(PujaFetcher):
    requests = 0

    def raw(self, url, redirects=0, check_redirect_robots=False):
        self.requests += 1
        return super().raw(url, redirects, check_redirect_robots)

    def prepare(self, url, receipt):
        self.target = url
        self.previous_validators = {k: header(receipt.get(k)) for k in ("etag", "last_modified")}
        self.metadata = {}
        self.condition = {}
        if receipt.get("content_hash"):
            etag, modified = header(receipt.get("etag")), header(receipt.get("last_modified"))
            if etag:
                self.condition = {"If-None-Match": etag}
            elif modified:
                self.condition = {"If-Modified-Since": modified}

    def conditional_headers(self, url):
        return self.condition if url == getattr(self, "target", None) else {}

    def observe_response(self, url, response):
        if url != getattr(self, "target", None):
            return
        if response.status in (200, 304):
            self.metadata = {
                "etag": header(response.getheader("ETag")),
                "last_modified": header(response.getheader("Last-Modified")),
            }
        if response.status == 304:
            if not self.condition:
                raise ValueError("unexpected_not_modified")
            self.metadata = {
                k: v or self.previous_validators.get(k) for k, v in self.metadata.items()
            }
            raise NotModified


def revision(html, source):
    soup = BeautifulSoup(html, "html.parser")
    if source.content_selector:
        nodes = soup.select(source.content_selector)
        if not nodes:
            raise ValueError("source_selector_missing")
        html = (
            "<main><p>"
            + html_escape.escape(" ".join(n.get_text(" ", strip=True) for n in nodes))
            + "</p></main>"
        )
    else:
        # Organizer pages sometimes put event venue/date details in their footer.
        # Retain it for monitoring, unlike the evidence-article body extractor.
        for node in soup.find_all(["footer", "main", "article"]):
            node.name = "section"
        # Structured event dates can change without changing the visible copy.
        for node in soup.select('script[type="application/ld+json"]'):
            try:
                value = json.dumps(json.loads(node.string or ""), sort_keys=True)
            except (ValueError, TypeError):
                continue
            node.name = "p"
            node.string = value
        html = str(soup)
    doc = freeze_document(html, str(source.url), source.language)
    text = " ".join(" ".join(p.original_text for p in doc.passages).split())
    if not text:
        raise ValueError("empty_source_text")
    return hashlib.sha256(unicodedata.normalize("NFC", text).encode()).hexdigest()


def due_sources(sources, receipts, at, limit):
    interval = timedelta(days=1 if at.month in (9, 10) else 7)

    def last(s):
        value = receipts.get(s.source_id, {}).get("last_attempt")
        try:
            parsed = datetime.fromisoformat(value) if value else datetime.min.replace(tzinfo=UTC)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (ValueError, TypeError):
            return datetime.min.replace(tzinfo=UTC)

    return sorted(
        (s for s in sources if s.enabled and at - last(s) >= interval),
        key=lambda s: (last(s), s.source_id),
    )[:limit]


def monitor(root, at=None, fetcher=None):
    import fcntl

    at = at or datetime.now(UTC)
    lock = root / ".cache/puja/refresh.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _monitor(root, at, fetcher)


def _monitor(root, at, fetcher):
    config = load_config(root)
    path = root / "data/puja_refresh.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    # Legacy extraction fingerprints are not evidence of source review.
    state = {"schema_version": "puja-monitor-1", "sources": old.get("sources", {})}
    receipts = state["sources"]
    selected = due_sources(config.sources, receipts, at, config.settings.max_sources_per_run)
    if not selected:
        return {"status": "not_due", "model_calls": 0, "checked": 0}
    if fetcher is None:
        policies = [
            SourcePolicy(
                name=s.publisher,
                domain=urlsplit(str(s.url)).hostname,
                tier="B",
                enabled=True,
                language=s.language,
                urls=[str(s.url)],
            )
            for s in selected
        ]
        fetcher = MonitorFetcher(policies, pipeline_settings(root))
        fetcher.missing_robots_hosts = {
            urlsplit(str(s.url)).hostname for s in selected if s.allow_missing_robots
        }
    summary = {
        "status": "checked",
        "model_calls": 0,
        "checked": 0,
        "unchanged": 0,
        "pending": 0,
        "failures": 0,
    }
    before = getattr(fetcher, "requests", 0)
    hosts = {}
    for source in selected:
        url = str(source.url)
        previous = receipts.get(source.source_id, {})
        if previous.get("url") != url:
            previous = {}
        current = {
            **previous,
            "url": url,
            "last_attempt": at.isoformat(),
            "last_reviewed_revision": source.reviewed_revision,
            "extraction_status": previous.get("extraction_status", "not_requested"),
        }
        receipts[source.source_id] = current
        dump(path, state)  # Reserve the attempt before network access, including failures.
        host = urlsplit(url).hostname
        wait = 1.1 - (time.monotonic() - hosts.get(host, 0))
        if wait > 0:
            time.sleep(wait)
        try:
            fetcher.prepare(url, previous)
            try:
                _, html = fetcher.article(url)
                digest = revision(html, source)
            except NotModified:
                digest = previous["content_hash"]
            unchanged = digest == previous.get("content_hash")
            current.update(
                content_hash=digest,
                last_success=at.isoformat(),
                status="checked",
                pending_change=digest != source.reviewed_revision,
                **{k: v for k, v in fetcher.metadata.items() if v},
            )
            # A new 200 response without validators invalidates old conditional headers.
            for key in ("etag", "last_modified"):
                if key not in fetcher.metadata or fetcher.metadata[key] is None:
                    current.pop(key, None)
            summary["unchanged"] += int(unchanged)
            summary["pending"] += int(current["pending_change"])
        except Exception as exc:
            current.update(status="unavailable", error=type(exc).__name__)
            summary["failures"] += 1
        finally:
            hosts[host] = time.monotonic()
        summary["checked"] += 1
        dump(path, state)
    summary["http_attempts"] = getattr(fetcher, "requests", 0) - before
    return summary


def public_checks(root):
    path = root / "data/puja_refresh.json"
    state = json.loads(path.read_text()) if path.exists() else {}
    return [
        dict(
            source_id=key,
            **{k: v for k, v in row.items() if k in {"url", "last_success", "pending_change"}},
        )
        for key, row in sorted(state.get("sources", {}).items())
    ]


def record_extraction(root, source_id, revision_id):
    """Explicit operator extraction updates its own status, never review/publication."""
    path = root / "data/puja_refresh.json"
    if not path.exists():
        return
    state = json.loads(path.read_text())
    row = state.get("sources", {}).get(source_id)
    if row:
        row.update(extraction_status="extracted", extracted_revision=revision_id)
        dump(path, state)
