import hashlib
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
    "inspection / visit only",
    "sample collected",
    "food discarded / destroyed",
    "seizure reported",
    "notice / advisory issued",
    "lab result reported",
    "multiple actions",
    "not reported",
    "other",
]
Confidence = Literal["unknown", "low", "medium", "high"]
EstablishmentContext = Literal[
    "restaurant / eatery",
    "chain / group",
    "mall / food court",
    "sweet shop / bakery",
    "market / vendor",
    "hotel / hospitality",
    "other",
    "unknown",
]
MenuContext = Literal["veg_only", "non_veg", "mixed", "unknown"]
MenuMethod = Literal[
    "publisher_explicit",
    "official_establishment_menu",
    "establishment_website",
    "reviewed_external_menu",
]
BusinessFormat = Literal["independent", "chain_group", "unknown"]
LocationPrecision = Literal["establishment", "street", "neighborhood", "city", "district"]
PublicationStatus = Literal[
    "active",
    "active_with_warning",
    "needs_review",
    "archived_unverifiable",
    "suspended",
    "superseded",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)

    @model_validator(mode="before")
    @classmethod
    def reject_sensitive(cls, value):
        reject_sensitive_fields(value)
        return value


class Source(StrictModel):
    source_id: str = ""
    source_revision_id: str = ""
    source_language: Literal["en", "bn", "und"] = "und"
    source_relationship: Literal["independent", "syndicated", "republication", "unknown"] = (
        "unknown"
    )
    origin_source_id: str | None = None
    evidence_span_hash: str = ""
    evidence_language: Literal["en", "bn", "und"] = "und"
    evidence_locator: Text | None = None
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

    @model_validator(mode="after")
    def identifiers(self):
        expected = {
            "source_id": "SRC-" + hashlib.sha256(self.source_url.encode()).hexdigest()[:20],
            "source_revision_id": self.text_sha256,
            "evidence_span_hash": hashlib.sha256(self.evidence_quote.encode()).hexdigest(),
        }
        for key, value in expected.items():
            if getattr(self, key) and getattr(self, key) != value:
                raise ValueError("source_provenance_mismatch")
            object.__setattr__(self, key, value)
        return self

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
    normalized_area: Text | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    location_precision: LocationPrecision | None = None
    location_source: URL | None = None
    location_method: Literal["reviewed_openstreetmap_geocode"] | None = None
    location_reviewed: bool = False
    action_category: Action = "not reported"
    action_category_source: URL | None = None
    action_category_method: Literal["publisher_explicit", "reviewed_source_context"] | None = None
    action_category_confidence: Confidence = "unknown"
    action_category_reviewed: bool = False
    establishment_context: EstablishmentContext = "unknown"
    establishment_context_source: URL | None = None
    establishment_context_method: (
        Literal["publisher_explicit", "reviewed_source_context"] | None
    ) = None
    establishment_context_confidence: Confidence = "unknown"
    establishment_context_reviewed: bool = False
    menu_context: MenuContext = "unknown"
    menu_context_source: URL | None = None
    menu_context_method: MenuMethod | None = None
    menu_context_confidence: Confidence = "unknown"
    menu_context_reviewed: bool = False
    business_format: BusinessFormat = "unknown"
    business_format_source: URL | None = None
    business_format_method: (
        Literal["publisher_explicit", "official_establishment_website", "reviewed_external_source"]
        | None
    ) = None
    business_format_confidence: Confidence = "unknown"
    business_format_reviewed: bool = False
    derived_context_sources: list[URL] = Field(default_factory=list, max_length=5)
    derived_context_method: Text = "Unknown; no contextual inference performed."
    derived_confidence: Confidence = "unknown"

    @model_validator(mode="after")
    def evidence_for_context(self):
        has_location = self.latitude is not None or self.longitude is not None
        if has_location and (
            self.latitude is None
            or self.longitude is None
            or not self.location_precision
            or not self.location_source
            or not self.location_method
            or not self.location_reviewed
        ):
            raise ValueError("location_context_requires_reviewed_source")
        if not has_location and any(
            [
                self.location_precision,
                self.location_source,
                self.location_method,
                self.location_reviewed,
            ]
        ):
            raise ValueError("unknown_location_must_not_claim_precision")
        groups = [
            (
                self.action_category != "not reported",
                self.action_category_source,
                self.action_category_method,
                self.action_category_confidence,
                self.action_category_reviewed,
            ),
            (
                self.establishment_context != "unknown",
                self.establishment_context_source,
                self.establishment_context_method,
                self.establishment_context_confidence,
                self.establishment_context_reviewed,
            ),
            (
                self.menu_context != "unknown",
                self.menu_context_source,
                self.menu_context_method,
                self.menu_context_confidence,
                self.menu_context_reviewed,
            ),
            (
                self.business_format != "unknown",
                self.business_format_source,
                self.business_format_method,
                self.business_format_confidence,
                self.business_format_reviewed,
            ),
        ]
        for active, source, method, confidence, reviewed in groups:
            if active and (
                not source or not method or confidence not in {"medium", "high"} or not reviewed
            ):
                raise ValueError("context_classification_requires_reviewed_evidence")
            if not active and (source or method or confidence != "unknown" or reviewed):
                raise ValueError("unknown_context_must_not_claim_evidence")
        return self


class LLMProvenance(StrictModel):
    llm_used: bool = False
    llm_provider: Text | None = None
    llm_model: Text | None = None
    llm_task: Text | None = None
    llm_pipeline_version: Text | None = None
    llm_output_was_validated: bool = False
    llm_task_version: Text | None = None
    llm_used_at: AwareDatetime | None = None
    source_revision_id: str | None = None
    fields_proposed: list[Text] = Field(default_factory=list, max_length=20)
    validation_result: Literal["not_used", "pending", "passed", "failed"] = "not_used"

    @model_validator(mode="after")
    def complete_provenance(self):
        if self.llm_used and not all(
            [
                self.llm_provider,
                self.llm_model,
                self.llm_task,
                self.llm_pipeline_version,
                self.llm_task_version,
                self.llm_used_at,
                self.source_revision_id,
                self.fields_proposed,
            ]
        ):
            raise ValueError("incomplete_llm_provenance")
        if self.llm_used and self.validation_result == "not_used":
            raise ValueError("missing_llm_validation_result")
        if not self.llm_used and (
            self.fields_proposed or self.validation_result != "not_used" or self.llm_used_at
        ):
            raise ValueError("unused_llm_must_not_claim_provenance")
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


class AutomaticValidation(StrictModel):
    method: Literal["explicit_inspection_sentence_v1", "explicit_inspection_sentence_v2"]
    validated_at: AwareDatetime
    pipeline_version: str


class ReviewedAssociation(StrictModel):
    source_url: URL
    relationship: Literal["independent", "syndicated", "republication", "unknown"]
    reviewed_at: AwareDatetime
    reviewer: Text
    event_match_checked: Literal[True]
    supported_fields: dict[str, Support]


class Event(StrictModel):
    superseded_by: Annotated[str, StringConstraints(pattern=r"^WBFS-[a-f0-9]{12}$")] | None = None
    reviewed_associations: list[ReviewedAssociation] = Field(default_factory=list, max_length=5)
    record_class: Literal["inspection_evidence"] = "inspection_evidence"
    record_scope: Literal[
        "establishment_event",
        "area_operation",
        "district_operation",
        "statewide_operation",
        "aggregate_report",
        "unknown",
    ] = "unknown"
    related_record_ids: list[Annotated[str, StringConstraints(pattern=r"^WBFS-[a-f0-9]{12}$")]] = (
        Field(default_factory=list, max_length=25)
    )
    establishment_id: Text | None = None
    location_id: Text | None = None
    first_published_at: AwareDatetime | None = None
    last_source_checked_at: AwareDatetime | None = None
    last_successful_evidence_check_at: AwareDatetime | None = None
    source_availability: Literal["available", "unavailable", "removed", "unknown"] = "unknown"
    source_availability_reason: Text | None = None
    evidence_support_status: Literal[
        "supported_as_of", "needs_review", "unsupported", "withdrawn"
    ] = "needs_review"
    publication_status: PublicationStatus = "needs_review"
    reviewer_hold: bool = False
    extractor_id: Text = "legacy_reviewed_extraction"
    extractor_version: Text = "1"
    validator_id: Text = "field_evidence_validation"
    validator_version: Text = "2"
    event_id: Annotated[str, StringConstraints(pattern=r"^WBFS-[a-f0-9]{12}$")]
    reported_fact: Facts
    derived_context: DerivedContext = Field(default_factory=DerivedContext)
    sources: list[Source] = Field(min_length=1, max_length=5)
    verification_status: Status = "PENDING REVIEW"
    verification_notes: Text = "Awaiting source and context review."
    display_summary: Text | None = None
    llm: LLMProvenance = Field(default_factory=LLMProvenance)
    review: Review | None = None
    automatic_validation: AutomaticValidation | None = None
    record_created_at: AwareDatetime
    record_updated_at: AwareDatetime
    pipeline_version: str = __version__
    history: list[Revision] = Field(min_length=1)
    is_fixture: bool = False
    context_notice: Literal[CONTEXT] = CONTEXT

    @model_validator(mode="before")
    @classmethod
    def legacy_lifecycle(cls, raw):
        if not isinstance(raw, dict) or "publication_status" in raw:
            return raw
        data = dict(raw)
        accepted = [
            h["at"]
            for h in data.get("history", [])
            if h.get("status") in {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"}
        ]
        current = data.get("verification_status") in {"SOURCE VERIFIED", "CROSS-SOURCE VERIFIED"}
        data.update(
            first_published_at=accepted[0] if accepted else None,
            publication_status="active" if current else "needs_review",
            evidence_support_status="supported_as_of" if current else "needs_review",
            source_availability="available" if current else "unknown",
            last_successful_evidence_check_at=accepted[-1] if accepted else None,
        )
        return data

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
        linked = {source.source_url for source in self.sources}
        for association in self.reviewed_associations:
            if association.source_url not in linked:
                raise ValueError("unlinked_source_association")
            source = next(s for s in self.sources if s.source_url == association.source_url)
            if source.source_relationship != association.relationship:
                raise ValueError("association_relationship_mismatch")
            for field, support in association.supported_fields.items():
                if (
                    field not in self.reported_fact.evidence
                    or support.source_url != source.source_url
                    or support.quote not in source.evidence_context
                ):
                    raise ValueError("unsupported_association_field")
        context = self.derived_context
        claimed = {
            context.action_category_source,
            context.establishment_context_source,
            context.menu_context_source,
            context.business_format_source,
            *context.derived_context_sources,
        } - {None}
        if not claimed.issubset(linked):
            raise ValueError("context_source_not_linked")
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


class ComplianceDocument(StrictModel):
    """URL-only pilot. No automatic publication or submitter contacts in this model."""

    record_id: Annotated[str, StringConstraints(pattern=r"^BFPC-[a-f0-9]{12}$")]
    record_class: Literal["licensing_compliance_document"] = "licensing_compliance_document"
    establishment_id: Text | None = None
    establishment_name: Text
    area: Text
    evidence_type: Literal[
        "licence",
        "compliance_certificate",
        "official_clearance",
        "regulatory_document",
        "corrective_action",
    ]
    issuer: Text
    document_date: date
    valid_from: date | None = None
    valid_until: date | None = None
    scope: Text
    source: Source
    document_status_as_reported: Text
    issuer_check_status: Literal["not_checked", "source_checked", "issuer_confirmed"] = (
        "not_checked"
    )
    publication_status: PublicationStatus = "needs_review"
    submission_id: Text | None = None
    submission_timestamp: AwareDatetime | None = None
    reviewed_at: AwareDatetime | None = None
    supported_fields: dict[str, Support]
    related_record_ids: list[Text] = Field(default_factory=list, max_length=10)
    supersedes: Text | None = None
    related_inspection_record: Text | None = None

    @model_validator(mode="after")
    def document_support(self):
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("invalid_validity_period")
        if self.publication_status in {"active", "active_with_warning"}:
            if not self.reviewed_at or self.issuer_check_status == "not_checked":
                raise ValueError("document_requires_manual_review")
            for field in [
                "establishment_name",
                "area",
                "issuer",
                "document_date",
                "scope",
                "document_status_as_reported",
                "valid_from",
                "valid_until",
            ]:
                value = getattr(self, field)
                if value is None:
                    continue
                support = self.supported_fields.get(field)
                if (
                    not support
                    or support.source_url != self.source.source_url
                    or support.quote not in self.source.evidence_context
                    or str(value) not in support.quote
                ):
                    raise ValueError("unsupported_document_field")
        return self
