# Data dictionary — schema 1.1.0

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
| llm | llm_used, llm_provider, llm_model, llm_task, llm_pipeline_version, llm_output_was_validated |
| review | Maintainer handle, timestamp, neutral note and explicit context/field attestations |
| record_created_at / record_updated_at | Timezone-aware record lifecycle timestamps |
| pipeline_version | Extractor/validator version |
| history | Ordered timestamps, statuses, notes and previous-version hashes |
| is_fixture | Blocks synthetic records from production publication |
| context_notice | Required non-removable disclaimer text in each record and export |

SOURCE VERIFIED and CROSS-SOURCE VERIFIED are the only publishable states. All other states are outside public statistical counts. No status asserts independent proof of the underlying event.

JSON is the authoritative download; CSV is a lossy convenience view and repeats attribution/disclaimer per row. Counts and dataset metadata accompany the JSON download. Pending queues, rejected candidates, source bodies and private history are never copied into the site build.

Missing values are null/unknown/not reported, never zero. A source publication date is displayed when an explicit event date is unavailable; the two remain distinct in the record. Sensitive/social identity fields, unsupported accusation/ranking fields and unknown fields are rejected rather than silently dropped.
