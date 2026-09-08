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
    discovery_method: Literal["curated_urls"] = "curated_urls"
    urls: list[URL] = Field(default_factory=list, max_length=20)
    feed_urls: list[URL] = Field(default_factory=list, max_length=2)
    discovery_pages: list[URL] = Field(default_factory=list, max_length=2)

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
    max_articles_per_run: int = Field(default=10, ge=1, le=10)
    max_pages_per_source: int = Field(default=5, ge=1, le=5)
    request_timeout_seconds: int = Field(default=15, ge=1, le=30)
    max_response_bytes: int = Field(default=524288, ge=1024, le=1048576)
    max_llm_calls_per_run: int = Field(default=5, ge=0, le=5)
    llm_enabled: bool = False
    auto_publish: bool = False
    repository_url: URL | None = None
    site_url: URL = "https://foodsafety.nemoneek.com/"


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
