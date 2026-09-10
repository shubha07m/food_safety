from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field, field_validator

from .models import URL, StrictModel

ROOT = Path(__file__).resolve().parents[2]


class SourcePolicy(StrictModel):
    name: str
    domain: str
    tier: Literal["A", "B", "C", "discovery"]
    enabled: bool = False
    language: Literal["en", "bn", "multilingual", "und"] = "und"
    discovery_method: Literal["curated_urls", "bounded_indexes", "manual_only"] = "curated_urls"
    discovery_status: Literal["active", "pilot", "manual_only", "blocked"] = "pilot"
    manual_only_reason: str | None = None
    urls: list[URL] = Field(default_factory=list, max_length=20)
    feed_urls: list[URL] = Field(default_factory=list, max_length=5)
    sitemap_urls: list[URL] = Field(default_factory=list, max_length=5)
    discovery_pages: list[URL] = Field(default_factory=list, max_length=5)

    @field_validator("domain")
    @classmethod
    def domain_only(cls, value):
        from urllib.parse import urlsplit

        from .safety import safe_url

        url = safe_url("https://" + value)
        if urlsplit(url).netloc != value:
            raise ValueError("exact_domain_required")
        return value


class Settings(StrictModel):
    max_articles_per_run: int = Field(default=20, ge=1, le=30)
    max_new_articles_per_run: int = Field(default=15, ge=1, le=25)
    max_rechecks_per_run: int = Field(default=5, ge=1, le=15)
    max_discovery_candidates_per_run: int = Field(default=80, ge=10, le=100)
    max_discovery_endpoints_per_run: int = Field(default=8, ge=1, le=15)
    max_pages_per_source: int = Field(default=5, ge=1, le=8)
    request_timeout_seconds: int = Field(default=15, ge=1, le=30)
    max_response_bytes: int = Field(default=524288, ge=1024, le=1048576)
    max_discovery_response_bytes: int = Field(default=1048576, ge=1024, le=1048576)
    max_llm_calls_per_run: int = Field(default=5, ge=0, le=5)
    llm_enabled: bool = True
    publish_from_llm: bool = True
    llm_provider: Literal["gemini"] = "gemini"
    llm_model: str = Field(default="gemini-3.5-flash-lite", pattern=r"^[a-z0-9.-]+$")
    llm_max_input_chars: int = Field(default=24000, ge=1000, le=60000)
    llm_max_output_tokens: int = Field(default=4096, ge=256, le=8192)
    llm_max_candidates: int = Field(default=12, ge=1, le=12)
    llm_input_usd_per_million: float = Field(default=0.10, ge=0)
    llm_output_usd_per_million: float = Field(default=0.40, ge=0)
    auto_publish: bool = True
    archive_after_days: int = Field(default=30, ge=7, le=90)
    review_after_days: int = Field(default=7, ge=1, le=30)
    community_submission_url: URL | None = None
    repository_url: URL | None = None
    site_url: URL = "https://foodsafety.nemoneek.com/"
    search_provider: Literal["none", "brave"] = "none"
    max_search_queries_per_run: int = Field(default=4, ge=0, le=6)

    @field_validator("community_submission_url")
    @classmethod
    def google_form_only(cls, value):
        from urllib.parse import urlsplit

        if value:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or not (
                (parsed.hostname == "forms.gle" and len(parsed.path) > 5)
                or (
                    parsed.hostname == "docs.google.com"
                    and parsed.path.startswith("/forms/d/e/")
                    and parsed.path.endswith("/viewform")
                )
            ):
                raise ValueError("expected_published_google_form_url")
        return value


def settings(root=ROOT):
    return Settings.model_validate(yaml.safe_load((root / "config/pipeline.yml").read_text()))


def sources(root=ROOT):
    raw = yaml.safe_load((root / "config/sources.yml").read_text())
    if set(raw) != {"sources"}:
        raise ValueError("invalid_source_config")
    result = [SourcePolicy.model_validate(item) for item in raw["sources"]]
    if len({p.domain for p in result}) != len(result):
        raise ValueError("duplicate_source_domain")
    return result
