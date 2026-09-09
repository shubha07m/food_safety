# Data dictionary — schema 1.2.0

## Provenance and lifecycle

Existing IDs and original evidence are preserved by `python -m food_safety.cli migrate`. First publication is derived from the earliest accepted history entry, never a restoration date. Legacy tombstones lacking that timestamp remain explicitly unknown until audited.

| Field | Meaning |
| --- | --- |
| record_class / record_scope | inspection_evidence; establishment_event, area_operation, district_operation, statewide_operation, aggregate_report or unknown |
| related_record_ids | Explicit links among operation/aggregate and individually supported records from the same reporting; never manufactured rows |
| first_published_at | First passed publication, immutable across restoration |
| last_source_checked_at | Latest attempt, not necessarily success |
| last_successful_evidence_check_at | Last adequate field-support check; determines 30-day active expiry |
| source_availability / reason | Transport state and bounded reason; no inference that reporting is false |
| evidence_support_status | supported_as_of, needs_review, unsupported, withdrawn |
| publication_status | active, active_with_warning, needs_review, archived_unverifiable, suspended, superseded |
| reviewer_hold | Prevents automatic semantic restoration |
| source_id / source_revision_id | Deterministic URL identity and extracted-text revision hash |
| source_language / evidence_language | en, bn or und; original quoted text preserved |
| evidence_span_hash / evidence_locator | Quote digest and optional locator; not full article storage |
| extractor / validator IDs and versions | Processing provenance, not model confidence |
| establishment_id / location_id | Optional reviewed identifiers, never inferred social identity |
| source_relationship / reviewed_associations | Independent, syndicated, republication or unknown; reviewed per-field alternative support |

`data/source_checks.json` persists minimal hashed source IDs, attempts, availability/reasons, retry times and supported-record check times across runners. It contains no article bodies or private submission content. Public lifecycle totals are generated in site/data/lifecycle.json; archived/suspended records appear only as minimal tombstones.

## Licensing & Compliance Documents pilot

ComplianceDocument is a separate URL-only model, not an inspection or quality score. It includes document identity/type, establishment/area, issuer/date, optional validity dates, scope, source metadata/original evidence, reported document status, issuer-check status, publication state, supported fields, review time and related/superseding IDs. Source URL/language/ID/retrieval time/original quote/hash are reused through the nested Source object rather than duplicated. Optional submission ID/time exclude contact details and internal reviewer notes. Only manually reviewed active documents may be exported. No real documents are currently published; no uploads or automatic business-submission publication exist.

Automatic records may carry `automatic_validation`: the evaluated deterministic
adapter method, validation timestamp and pipeline version. This is separate from
`review` and never means a maintainer read the source. Every automatically
published field still needs exact source support and all publication gates.
The public source-verification meaning is unchanged.

The authoritative executable schema is src/food_safety/models.py. Unknown fields are rejected at every model boundary. Published and pending files use generated_at, schema_version, pipeline_version, record_count, context_notice and records. Rejected records retain only candidate_id, at and a controlled reason code; article content is discarded.

| Field | Meaning |
| --- | --- |
| event_id | Stable WBFS- plus 12 hexadecimal characters; preserved across revisions |
| reported_fact | Attributed factual fields, structurally separate from all derived context |
| event_date | ISO YYYY-MM-DD event date, distinct from article publication date |
| area / district | Coarse reported location; no personal address |
| establishment_name / establishment_type | Source-stated business identity/type, null if unknown |
| reported_observation / reported_action | Exact source-supported statements; no project finding |
| reported_quantity / reported_authority | Exact source-stated quantity/unit and authority; nullable |
| legal_finding_status | unknown by default; official_finding_reported needs formal_finding and Tier A evidence. none_reported is reserved and blocked from publication to avoid unsupported absence assertions |
| formal_finding | Optional explicit authoritative statement, never inferred from an inspection |
| evidence | Map of factual field name to source_url and exact quote |
| sources | All distinct supporting sources, preserving independent provenance |
| source_url / source_title / source_publisher | Canonical original link, article title and publisher |
| source_date | Article publication date if established, otherwise null |
| source_type / tier | official/news/other/discovery and configured A/B/C/discovery tier |
| retrieved_at / text_sha256 | UTC retrieval timestamp and SHA-256 of normalized extracted text |
| evidence_quote / evidence_context | Exact minimal span plus necessary surrounding context; 25-word quote, 60-word context, and 250-word aggregate source budget |
| archive_url | Optional existing appropriate archive link; never automatically created |
| verification_status / verification_notes | Explicit review/source state and neutral explanatory note |
| derived_context | Contextual metadata; never part of reported_fact |
| display_summary | Deterministic neutral public copy generated only from validated structured fields |
| normalized_area | Reviewed geographic normalization; never a fabricated coordinate |
| latitude / longitude / location_precision | Optional reviewed coarse OpenStreetMap area anchor; never an establishment address or geographic-prevalence claim. |
| location_source / location_method / location_reviewed | Required provenance for every coordinate; ambiguous and district-only locations remain unmapped. |
| action_category | Reviewed grouping: inspection/visit only, sample collected, food discarded/destroyed, seizure reported, notice/advisory, lab result, multiple actions, not reported or other |
| establishment_context | restaurant/eatery, chain/group, mall/food court, sweet shop/bakery, market/vendor, hotel/hospitality, other or unknown |
| menu_context | veg_only, non_veg, mixed or unknown |
| menu context provenance | Source, allowed method, confidence and reviewed flag; required for non-unknown values |
| business_format | independent, chain_group or unknown; distinct from establishment type and personal ownership identity |
| business-format provenance | Source, allowed method, confidence and reviewed flag; names and cuisine are not evidence |
| contextual provenance | Every non-default action or establishment classification also carries linked evidence provenance and maintainer review |
| llm | Provider/model/task/version, use time, source revision, proposed fields and validation outcome; model output never bypasses evidence validation |
| review | Maintainer handle, timestamp, neutral note and explicit context/field attestations |
| record_created_at / record_updated_at | Timezone-aware record lifecycle timestamps |
| pipeline_version | Extractor/validator version |
| history | Ordered timestamps, statuses, notes and previous-version hashes |
| is_fixture | Blocks synthetic records from production publication |
| context_notice | Required non-removable disclaimer text in each record and export |

SOURCE VERIFIED and CROSS-SOURCE VERIFIED are the only publishable states. All other states are outside public statistical counts. No status asserts independent proof of the underlying event.

JSON is the authoritative download; CSV is a lossy convenience view and repeats attribution/disclaimer per row. Counts and dataset metadata accompany the JSON download. Pending queues, rejected candidates, source bodies and private history are never copied into the site build.

Missing values are null/unknown/not reported, never zero. A source publication date is displayed when an explicit event date is unavailable; the two remain distinct in the record. Sensitive/social identity fields, unsupported accusation/ranking fields and unknown fields are rejected rather than silently dropped.
