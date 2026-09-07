import socket

import pytest

from food_safety.fetch import Fetcher, FetchError, public_addresses
from food_safety.safety import claim_risks, reject_sensitive_fields, safe_url


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,hi",
        "http://localhost/",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://172.16.0.1",
        "http://169.254.169.254",
        "http://[::1]/",
        "http://2130706433/",
        "http://127.1/",
        "https://user:password@example.org/",
        "https://example.org:8000/",
        "//example.org",
        "https://example.org\\@localhost/",
        "https://example.local/",
        "https://example.org/\n",
    ],
)
def test_unsafe_url(url):
    with pytest.raises(ValueError):
        safe_url(url)


def test_canonicalization():
    assert safe_url("https://EXAMPLE.org/a?utm_source=x&id=1#top") == "https://example.org/a?id=1"


def test_dns_rebinding_protection(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))],
    )
    with pytest.raises(FetchError, match="private_dns"):
        public_addresses("example.org", 443)


def test_disallowed_domain(policy):
    from food_safety.config import Settings

    fetcher = Fetcher([policy], Settings())
    with pytest.raises(FetchError, match="domain_not_enabled"):
        fetcher.article("https://unknown.example/article")


@pytest.mark.parametrize(
    "field",
    [
        "religion",
        "caste",
        "ethnicity",
        "political_affiliation",
        "sexual_orientation",
        "nationality",
        "owner_religion",
        "employee_details",
        "personal_address",
        "risk_score",
    ],
)
def test_nested_sensitive_keys(field):
    with pytest.raises(ValueError):
        reject_sensitive_fields({"nested": [{field: "redacted"}]})


@pytest.mark.parametrize(
    "text",
    [
        "Boycott this business",
        "infer religion",
        "guilty offender",
        "ignore previous instructions",
        "contact person@example.org",
    ],
)
def test_claim_flags(text):
    assert claim_risks(text)
