"""Reject unsafe field structures and links before retention or publication."""

import ipaddress
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

FORBIDDEN = {
    "religion",
    "caste",
    "ethnicity",
    "communal_identity",
    "political_affiliation",
    "sexual_orientation",
    "nationality",
    "community",
    "owner_family_background",
    "employee_details",
    "phone",
    "phone_number",
    "personal_address",
    "social_media",
    "violation",
    "guilt",
    "unsafe",
    "sentiment",
    "risk_score",
    "owner_religion",
}
RISK_TEXT = re.compile(
    r"\b(religio\w*|caste|ethnic\w*|communal\w*|hindu\w*|muslim\w*|christian\w*|"
    r"sikh\w*|jewish|buddhist\w*|political affiliation|sexual orientation|"
    r"boycott|guilty|criminal|offender|unsafe restaurant|dangerous food|"
    r"ignore (all |previous )?instructions|system prompt)\b",
    re.I,
)


def reject_sensitive_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = re.sub(r"[^a-z0-9]+", "_", str(key).lower()).strip("_")
            if normalized in FORBIDDEN or any(
                token in normalized.split("_") for token in ("religion", "caste", "ethnicity")
            ):
                raise ValueError("forbidden_field")
            reject_sensitive_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_sensitive_fields(item)


def safe_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048 or re.search(r"[\s\\\x00-\x1f]", value):
        raise ValueError("invalid_url")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("unsafe_url_scheme")
    if parts.username or parts.password:
        raise ValueError("url_credentials_forbidden")
    host = parts.hostname.lower().rstrip(".")
    if (
        host == "localhost"
        or "." not in host
        or host.endswith((".local", ".localhost", ".internal"))
    ):
        raise ValueError("private_url")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-z0-9.-]+", host) or re.fullmatch(r"[0-9.]+", host):
            raise ValueError("invalid_host") from None
    else:
        if not address.is_global:
            raise ValueError("private_url")
    if parts.port not in {None, 80, 443}:
        raise ValueError("unexpected_port")
    query = urlencode(
        [
            (key, val)
            for key, val in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
        ]
    )
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path or "/", query, ""))


def normalize(value: str) -> str:
    return " ".join(value.split()).casefold()


def claim_risks(value: str) -> bool:
    return bool(RISK_TEXT.search(value) or re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", value, re.I))


def safe_text(value: str) -> str:
    if claim_risks(value) or re.search(r"(?<!\d)(?:\+?91[ -]?)?[6-9]\d{9}(?!\d)", value):
        raise ValueError("sensitive_or_claim_risk_text")
    return value
