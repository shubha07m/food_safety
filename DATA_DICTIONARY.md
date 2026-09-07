# Data dictionary — schema 1.0.0

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
| legal_finding_status | unknown by default; official_finding_reported needs formal_finding and Tier A evidence. none_reported is reserved and blocked from V1 publication to avoid unsupported absence assertions |
| formal_finding | Optional explicit authoritative statement, never inferred from an inspection |
| evidence | Map of factual field name to source_url and exact quote |
| sources | All distinct supporting sources, preserving independent provenance |
| source_url / source_title / source_publisher | Canonical original link, article title and publisher |
| source_date | Article publication date if established, otherwise null |
| source_type / tier | official/news/other/discovery and configured A/B/C/discovery tier |
| retrieved_at / text_sha256 | UTC retrieval timestamp and SHA-256 of normalized extracted text |
| evidence_quote / evidence_context | Exact minimal span plus necessary surrounding context; 25-word aggregate source budget |
| archive_url | Optional existing appropriate archive link; never automatically created |
| verification_status / verification_notes | Explicit review/source state and neutral explanatory note |
| derived_context | Contextual metadata; never part of reported_fact |
| derived_menu_category | veg, non-veg, both, unknown; requires public supporting context |
| derived_owner_category | Business format only: independent, chain/group, mall/food court, market/vendor, unknown; no personal owner identity |
| action_category | Reviewed grouping: inspection only, sample collected, food discarded, seizure reported, notice reported, laboratory result reported, other |
| derived_geography | Optional reviewed geographic normalization |
| derived_context_sources / method / confidence | Supporting URLs, explicit classification method and unknown/low/medium/high confidence |
| llm | llm_used, llm_provider, llm_model, llm_task, llm_pipeline_version, llm_output_was_validated |
| review | Maintainer handle, timestamp, neutral note and explicit context/field attestations |
| record_created_at / record_updated_at | Timezone-aware record lifecycle timestamps |
| pipeline_version | Extractor/validator version |
| history | Ordered timestamps, statuses, notes and previous-version hashes |
| is_fixture | Blocks synthetic records from production publication |
| context_notice | Required non-removable disclaimer text in each record and export |

SOURCE VERIFIED and CROSS-SOURCE VERIFIED are the only publishable V1 states. All other states are outside public statistical counts. No status asserts independent proof of the underlying event.

JSON is the authoritative download; CSV is a lossy convenience view and repeats attribution/disclaimer per row. Counts and dataset metadata accompany the JSON download. Pending queues, rejected candidates, source bodies and private history are never copied into the site build.

Missing values are null/unknown, never zero. Dates currently require exact ISO evidence; reviewed date-format normalization is future work. Sensitive/social identity fields, unsupported accusation/ranking fields and unknown fields are rejected rather than silently dropped.
