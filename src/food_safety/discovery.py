"""Bounded URL discovery. Leads are never evidence and never publish directly."""

import json
import os
import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from .safety import safe_url

TERMS = re.compile(
    r"food[-\s].{0,45}(?:safety|inspect|sample)|restaurant.{0,40}inspect|"
    r"KMC.{0,40}food|FSSAI.{0,40}(?:inspect|sample)|"
    r"খাদ্য.{0,25}(?:সুরক্ষা|নিরাপত্তা|ভেজাল|পরীক্ষা)|"
    r"খাবার.{0,30}(?:অভিযান|নমুনা|বাসি|অস্বাস্থ্যকর)|"
    r"রেস্ত(?:ো|ে)রাঁ.{0,35}(?:পরিদর্শন|অভিযান|লাইসেন্স)|"
    r"লাইসেন্স.{0,25}(?:বাতিল|সাসপেন্ড)|বাসি[- ]পচা",
    re.I,
)

SEARCH_TERMS = (
    "food safety Kolkata",
    "food inspection West Bengal",
    "খাদ্য সুরক্ষা কলকাতা",
    "রেস্তোরাঁ অভিযান পশ্চিমবঙ্গ",
)


@dataclass(frozen=True)
class Lead:
    url: str
    mechanism: str


def relevant_lead(text):
    return bool(TERMS.search(" ".join(text.split())))


def _same_domain(raw, policy, base):
    try:
        url = safe_url(urljoin(base, raw))
    except ValueError:
        return None
    return url if urlsplit(url).hostname == policy.domain else None


def page_candidates(body, policy, limit):
    result = []
    base = f"https://{policy.domain}/"
    for anchor in BeautifulSoup(body, "html.parser").find_all("a", href=True)[:2500]:
        label = anchor.get_text(" ", strip=True) + " " + anchor["href"]
        if not relevant_lead(label):
            continue
        url = _same_domain(anchor["href"], policy, base)
        if url and url not in result:
            result.append(url)
        if len(result) >= limit:
            break
    return result


def feed_candidates(body, policy, limit):
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", body, re.I):
        raise ValueError("feed_declarations_not_allowed")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid_feed") from exc
    result = []
    for item in list(root.iter())[:2500]:
        if item.tag.rsplit("}", 1)[-1] not in {"item", "entry"}:
            continue
        if not relevant_lead(" ".join(item.itertext())):
            continue
        for child in item:
            if child.tag.rsplit("}", 1)[-1] == "link":
                url = _same_domain(
                    child.get("href") or child.text or "", policy, f"https://{policy.domain}/"
                )
                if url and url not in result:
                    result.append(url)
        if len(result) >= limit:
            break
    return result[:limit]


def sitemap_candidates(body, policy, limit):
    """Parse configured URL/news sitemaps; never recursively follow sitemap indexes."""
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", body, re.I):
        raise ValueError("sitemap_declarations_not_allowed")
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as exc:
        raise ValueError("invalid_sitemap") from exc
    result = []
    for node in list(root)[:5000]:
        if node.tag.rsplit("}", 1)[-1] != "url":
            continue
        values = {child.tag.rsplit("}", 1)[-1]: (child.text or "") for child in node.iter()}
        loc = values.get("loc", "")
        if not relevant_lead(" ".join(values.values())):
            continue
        url = _same_domain(loc, policy, f"https://{policy.domain}/")
        if url and url not in result:
            result.append(url)
        if len(result) >= limit:
            break
    return result


class BraveSearch:
    """Optional documented API integration; disabled without explicit config and secret."""

    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, policies, max_queries=4, client=None):
        self.domains = {p.domain: p for p in policies if p.enabled and p.tier in {"A", "B"}}
        self.key = os.environ.get("BRAVE_SEARCH_API_KEY", "")
        if not self.key:
            raise ValueError("missing_brave_search_api_key")
        self.max_queries = min(max_queries, 6)
        self.client = client

    def discover(self, limit):
        client = self.client or httpx.Client(timeout=15, follow_redirects=False, trust_env=False)
        found = []
        try:
            for query in SEARCH_TERMS[: self.max_queries]:
                response = client.get(
                    self.endpoint,
                    params={"q": query, "count": min(20, limit)},
                    headers={"X-Subscription-Token": self.key, "Accept": "application/json"},
                )
                response.raise_for_status()
                if len(response.content) > 262144:
                    raise ValueError("search_response_too_large")
                rows = json.loads(response.content).get("web", {}).get("results", [])
                for row in rows:
                    try:
                        url = safe_url(row.get("url", ""))
                    except ValueError:
                        continue
                    policy = self.domains.get(urlsplit(url).hostname)
                    if policy and (policy, url) not in found:
                        found.append((policy, url))
                    if len(found) >= limit:
                        return found
            return found
        finally:
            if self.client is None:
                client.close()
