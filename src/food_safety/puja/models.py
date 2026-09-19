from datetime import date
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl, model_validator

from ..places.models import ID, Latitude, Longitude


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Settings(Strict):
    refresh_runs_per_day: int = Field(default=4, ge=1, le=10)
    max_sources_per_run: int = Field(default=5, ge=1, le=10)
    max_model_calls_per_run: int = Field(default=3, ge=0, le=5)
    max_candidates_per_source: int = Field(default=30, ge=1, le=50)


class SourceSpec(Strict):
    source_id: ID
    url: HttpUrl
    publisher: str = Field(min_length=1, max_length=160)
    language: Literal["en", "bn", "multilingual", "und"] = "und"
    enabled: bool = True
    allow_missing_robots: bool = False
    content_selector: str | None = Field(default=None, max_length=160)


class SourceEvidence(Strict):
    source_url: HttpUrl
    source_title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=160)
    publication_date: date | None = None
    quote: str = Field(min_length=1, max_length=600)
    source_revision_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class PandalRecord(Strict):
    pandal_id: ID
    region_id: ID = "kolkata"
    country_code: str = Field(default="IN", pattern=r"^[A-Z]{2}$")
    admin1: str = "West Bengal"
    metro_region: str | None = Field(default=None, max_length=160)
    name: str = Field(min_length=1, max_length=200)
    name_bn: str | None = Field(default=None, max_length=200)
    aliases: list[str] = Field(default_factory=list, max_length=20)
    area: str = Field(min_length=1, max_length=160)
    neighborhood: str | None = Field(default=None, max_length=160)
    city: str = Field(min_length=1, max_length=160)
    venue: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    event_dates: str | None = Field(default=None, max_length=160)
    district: str | None = Field(default=None, min_length=1, max_length=160)
    location_precision: Literal["locality", "source_zone"] = "locality"
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    coordinate_source: HttpUrl | None = None
    coordinate_precision: Literal["venue", "street", "neighborhood"] | None = None
    organizer: str | None = Field(default=None, max_length=200)
    year: int | None = Field(default=None, ge=1900, le=2100)
    featured: bool = False
    subtitle: str | None = Field(default=None, max_length=180)
    sources: list[SourceEvidence] = Field(min_length=1, max_length=10)
    verification_status: Literal["SOURCE VERIFIED"] = "SOURCE VERIFIED"
    last_verified_at: AwareDatetime

    @model_validator(mode="after")
    def provenance(self):
        if self.name.casefold() in {"puja name", "pandal name", "name"}:
            raise ValueError("table_header_is_not_a_pandal")
        if len({a.casefold() for a in self.aliases + [self.name]}) != len(self.aliases) + 1:
            raise ValueError("duplicate_alias")
        coordinates = (self.latitude, self.longitude)
        if (coordinates[0] is None) != (coordinates[1] is None):
            raise ValueError("coordinate_pair_required")
        if coordinates[0] is not None and (
            not self.coordinate_source or not self.coordinate_precision
        ):
            raise ValueError("coordinate_provenance_required")
        if self.coordinate_source and any(
            value in self.coordinate_source.host.lower()
            for value in ("google", "gstatic", "goo.gl")
        ):
            raise ValueError("independent_coordinate_source_required")
        return self


class Config(Strict):
    schema_version: Literal["puja-curation-1"] = "puja-curation-1"
    settings: Settings = Field(default_factory=Settings)
    sources: list[SourceSpec] = Field(default_factory=list, max_length=100)
    published: list[PandalRecord] = Field(default_factory=list, max_length=500)

    @model_validator(mode="after")
    def unique(self):
        for values in ([s.source_id for s in self.sources], [p.pandal_id for p in self.published]):
            if len(values) != len(set(values)):
                raise ValueError("duplicate_id")
        return self


class SupportedValue(Strict):
    raw_value: str = Field(min_length=1, max_length=300)
    passage_id: str = Field(pattern=r"^P\d{3,5}$")
    original_quote: str = Field(min_length=1, max_length=1200)


class Candidate(Strict):
    candidate_id: str = Field(pattern=r"^C\d{1,3}$")
    name: SupportedValue
    name_bn: SupportedValue | None = None
    aliases: list[SupportedValue] = Field(default_factory=list, max_length=20)
    area: SupportedValue
    neighborhood: SupportedValue | None = None
    city: SupportedValue
    district: SupportedValue | None = None
    organizer: SupportedValue | None = None
    year: SupportedValue | None = None
    latitude: SupportedValue | None = None
    longitude: SupportedValue | None = None


class Extraction(Strict):
    completion_status: Literal["complete", "no_candidates", "incomplete"]
    candidates: list[Candidate] = Field(default_factory=list, max_length=50)


class PublicData(Strict):
    schema_version: Literal["puja-1"] = "puja-1"
    generated_from: Literal["source_verified_curated_config"] = "source_verified_curated_config"
    record_count: int = Field(ge=0)
    records: list[PandalRecord]
    coverage: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def count(self):
        if self.record_count != len(self.records):
            raise ValueError("record_count_mismatch")
        return self
