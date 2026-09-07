from datetime import date
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from . import CONTEXT, SCHEMA_VERSION, __version__
from .safety import reject_sensitive_fields, safe_text, safe_url

Text = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=600),
    AfterValidator(safe_text),
]
URL = Annotated[str, AfterValidator(safe_url)]
Status = Literal[
    "SOURCE VERIFIED",
    "CROSS-SOURCE VERIFIED",
    "SINGLE SOURCE",
    "PENDING REVIEW",
    "SOURCE UPDATED",
    "DISPUTED",
    "SOURCE WITHDRAWN",
    "SUPERSEDED",
    "REJECTED",
]
Action = Literal[
    "inspection only",
    "sample collected",
    "food discarded",
    "seizure reported",
    "notice reported",
    "laboratory result reported",
    "other",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive(cls, value):
        reject_sensitive_fields(value)
        return value


class Source(StrictModel):
    source_url: URL
    source_title: Text
    source_publisher: Text
    source_date: date | None = None
    source_type: Literal["official", "news", "other", "discovery"]
    tier: Literal["A", "B", "C", "discovery"]
    retrieved_at: AwareDatetime
    text_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    evidence_quote: Text
    evidence_context: Text
    archive_url: URL | None = None

    @field_validator("evidence_quote")
    @classmethod
    def short_quote(cls, value):
        if len(value.split()) > 25:
            raise ValueError("Evidence quote must contain at most 25 words")
        return value

    @field_validator("evidence_context")
    @classmethod
    def short_context(cls, value):
        if len(value.split()) > 60:
            raise ValueError("Evidence context must contain at most 60 words")
        return value


class Support(StrictModel):
    source_url: URL
    quote: Text


class Facts(StrictModel):
    event_date: date | None = None
    area: Text | None = None
    district: Text | None = None
    establishment_name: Text | None = None
    establishment_type: Text | None = None
    reported_observation: Text
    reported_action: Text | None = None
    reported_quantity: Text | None = None
    reported_authority: Text | None = None
    legal_finding_status: Literal["none_reported", "official_finding_reported", "unknown"] = (
        "unknown"
    )
    formal_finding: Text | None = None
    # Every factual value has its own evidence span, keyed by field name.
    evidence: dict[str, Support]


class DerivedContext(StrictModel):
    derived_menu_category: Literal["veg", "non-veg", "both", "unknown"] = "unknown"
    derived_owner_category: Literal[
        "independent", "chain/group", "mall/food court", "market/vendor", "unknown"
    ] = "unknown"
    derived_geography: Text | None = None
    action_category: Action = "other"
    derived_context_sources: list[URL] = Field(default_factory=list, max_length=5)
    derived_context_method: Text = "Unknown; no contextual inference performed."
    derived_confidence: Literal["unknown", "low", "medium", "high"] = "unknown"


class LLMProvenance(StrictModel):
    llm_used: bool = False
    llm_provider: Text | None = None
    llm_model: Text | None = None
    llm_task: Text | None = None
    llm_pipeline_version: Text | None = None
    llm_output_was_validated: bool = False

    @model_validator(mode="after")
    def complete_provenance(self):
        if self.llm_used and not all(
            [self.llm_provider, self.llm_model, self.llm_task, self.llm_pipeline_version]
        ):
            raise ValueError("incomplete_llm_provenance")
        return self


class Revision(StrictModel):
    at: AwareDatetime
    status: Status
    note: Text
    previous_record_sha256: str | None = None


class Review(StrictModel):
    reviewed_at: AwareDatetime
    reviewer: Text  # Maintainer handle; no personal contact details.
    note: Text
    source_context_checked: bool
    all_fields_supported: bool


class Event(StrictModel):
    event_id: Annotated[str, StringConstraints(pattern=r"^WBFS-[a-f0-9]{12}$")]
    reported_fact: Facts
    derived_context: DerivedContext = Field(default_factory=DerivedContext)
    sources: list[Source] = Field(min_length=1, max_length=5)
    verification_status: Status = "PENDING REVIEW"
    verification_notes: Text = "Awaiting source and context review."
    llm: LLMProvenance = Field(default_factory=LLMProvenance)
    review: Review | None = None
    record_created_at: AwareDatetime
    record_updated_at: AwareDatetime
    pipeline_version: str = __version__
    history: list[Revision] = Field(min_length=1)
    is_fixture: bool = False
    context_notice: Literal[CONTEXT] = CONTEXT

    @model_validator(mode="after")
    def consistency(self):
        if len({s.source_url for s in self.sources}) != len(self.sources):
            raise ValueError("duplicate_source")
        if self.record_updated_at < self.record_created_at:
            raise ValueError("invalid_record_timestamps")
        if self.history[-1].status != self.verification_status:
            raise ValueError("history_status_mismatch")
        if self.history[-1].at != self.record_updated_at:
            raise ValueError("history_timestamp_mismatch")
        return self


class Dataset(StrictModel):
    generated_at: AwareDatetime
    schema_version: Literal[SCHEMA_VERSION] = SCHEMA_VERSION
    pipeline_version: Literal[__version__] = __version__
    record_count: int = Field(ge=0)
    context_notice: Literal[CONTEXT] = CONTEXT
    records: list[Event]

    @model_validator(mode="after")
    def counts(self):
        if self.record_count != len(self.records):
            raise ValueError("record_count_mismatch")
        if len({r.event_id for r in self.records}) != self.record_count:
            raise ValueError("duplicate_event_id")
        return self
