# Methodology

Public beta at https://foodsafety.nemoneek.com/ . The repository contains an initial public-source sample. The preserved HTML prototype and synthetic test fixtures are not evidence.

## Coarse geographic context

Where an unambiguous reported area can be independently located, the tracker may show a reviewed OpenStreetMap reference coordinate with an explicit precision label. These are area anchors, not establishment addresses, inspection locations or evidence of geographic prevalence. Ambiguous or district-only areas remain unmapped.

## Unit of observation and scope

A record describes one source-supported reported event, with a date and area confirmed before publication. West Bengal is the geographic scope, initially emphasizing Kolkata and nearby areas. Maintainers must check geographic relevance. An establishment may be unnamed. Multiple establishments in one article require separate, correctly attributed evidence; the deterministic extractor never assigns an article-wide quantity or action to individual businesses.

Event date and publication date are distinct. Missing publication dates and quantities remain null. Event dates require explicit supporting date evidence; a source publication date may be retained separately when the event date is not established. This conservative limitation avoids invented dates.

## Processing and review

Bounded publisher indexes, feeds, configured sitemaps, curated URLs, optional permitted search API results and approved community leads → canonicalization → bounded robots-aware fetch → article-text extraction → candidate extraction → per-field evidence checks → sensitive-content checks → conservative association → source-policy checks → pending review or publication → aggregates → static site.

The pipeline has no recursive crawler or search-result HTML scraping. A run may discover up to 80 unique URLs and process at most 20 new/due articles (hard ceiling 30), with separate new-discovery and source-revalidation budgets. Discovery pages, feeds, sitemaps and search results are never evidence. New-record admission fails closed on retrieval failure, missing evidence, suspicious extracted fields or uncertain attribution. Existing records follow the bounded-continuity policy below. Article bodies exist only in memory during routine processing.

There are two publication paths. A maintainer may prepare a schema-valid record and explicitly attest to checking original context and every displayed field; the review command freshly checks sources. Separately, narrow deterministic English/Bengali adapters can publish explicit inspection statements containing a supported authority, action and reviewed West Bengal locality. Structured page metadata must establish the source publication date. Exact per-field evidence, an accessible Tier A/B source, safe surrounding context, valid schema and no unresolved duplicate are required. Explicit aggregate quantities create one operation-level record, never the stated number of establishments. Explicitly named establishments may create linked establishment records only when the same bounded span associates each name with the action. Missing values remain unknown. Publication date is not event date.

The config enables the evaluated adapter; the scheduled workflow sets AUTO_PUBLISH=true. Local execution still requires this explicit environment opt-in. Every record must pass publication validation. Automatic records carry automatic_validation provenance, not a fabricated human-review attestation. Ambiguous candidates stay pending or are rejected. The adapter is intentionally narrow: there is no promise that every new article will yield a published record. Maintainers periodically audit new records. Complex attribution, negation, source corrections, menu/business context and legal findings require human review.

## Evidence lifecycle — version 2

Transport failure changes availability. Material uncertainty changes review status. Evidence failure changes publication eligibility. Prolonged unverifiability changes active visibility, not historical truth.

New records need accessible permitted sources, source identity, exact field evidence, date/location support, safe attribution and deduplication. Publication remains strict. English and Bengali deterministic adapters accept only narrowly supported structures; Bengali original text is never replaced by translated evidence.

Source availability (available/unavailable/removed/unknown), evidence support (supported_as_of/needs_review/unsupported/withdrawn), and publication status are separate. SOURCE VERIFIED means the source supported the statement at the recorded check time, not independent proof. A warning retains prior support and its date; no "likely supported" label is used.

| Observation | Publication outcome |
| --- | --- |
| Timeout, 403, DNS, robots or technical extraction failure | active_with_warning; preserve dated evidence |
| Full-page hash changes, retained context and identity still valid | active; retain revision provenance |
| Relevant correction, meaning or entity relationship uncertain | needs_review; exclude from active analytics |
| Article explicitly withdrawn | suspended; minimal public status only |
| No adequate evidence revalidation for 30 days | archived_unverifiable; not disproved |
| Technical warning resolves with unchanged valid support | automatic active restoration, same ID and first publication |
| Semantic hold or suspension | human review required; retrieval alone never restores |
| Reviewed corrected replacement | superseded with explicit replacement relationship |

One canonical URL is checked once per run for its dependent records. Source checks retain bounded reason codes, failure count, attempt/success times and retry eligibility, not article bodies. Retries back off 4, 12 and 24 hours, then daily through day seven and weekly thereafter. Retry-After can lengthen these intervals. Three failures over seven days flag review. Two host failures open a per-run circuit breaker. Missed runs do not refresh timestamps. Thirty-day expiry is measured from the last successful adequate evidence check, including a stalled scheduler.

Evidence decisions are record-specific: a clearly scoped correction affects its named record; unscoped corrections conservatively hold dependent records. Retaining an exact quote is insufficient if nearby new negation changes its meaning. Missing context or changed title/identity requires review, not automatic accusations. Full hashes remain provenance rather than sole suspension triggers. A known source redirect requires reassessment; arbitrary redirects are never trusted as a new identity.

Ever published counts unique prior publications, including active and non-active records. Active includes active_with_warning. Restored records are not new publications. New in seven days uses first_published_at. Suspended/archive pages retain minimal ID/status/history metadata, not disputed claims. No community backlog is shown without a durable queue. Public exports include warning, availability and verification-date fields.

Reviewed cross-source associations link each displayed field to a short source span and explicit event-match/independence attestations. Independent paraphrases may have different wording, but are never fuzzy auto-merged. Distinct publisher names alone do not prove independence. An unreviewed additional association does not replace an existing accepted record. Complex semantic decisions still need a maintainer.

## Source tier interpretation

A: official authority material. B: established identifiable news publishers with accessible articles. C: identifiable publications requiring stronger corroboration; the current policy retains candidates for research but does not publish Tier C evidence. Discovery: snippets, aggregators, social media or other weak material; never fetched into the publication pipeline.

SOURCE VERIFIED: source existence, quoted support and context reviewed, not independent proof of the event. CROSS-SOURCE VERIFIED: independent publishers support the displayed observation; not proof of real-world truth. Review defaults to SOURCE VERIFIED even with multiple sources.

SINGLE SOURCE and PENDING REVIEW are not public acceptance states. SOURCE UPDATED, DISPUTED, SOURCE WITHDRAWN, SUPERSEDED and REJECTED are held out of public statistics. A failed later source check suspends the affected public record. Partial scans do not establish that every record was recently checked.

## Evidence, provenance and revisions

Every non-null fact has a supporting source URL and exact short quote in reported_fact.evidence. Quotes must sit inside a retained context span that matches fetched text. The text hash records which extracted version was reviewed, without retaining a full copyrighted article. An evidence quote is capped at 25 words; its necessary context is capped at 60 words; retained maximal contexts total at most 250 words per canonical source across the public dataset. These are conservative engineering budgets, not a legal safe harbour. When an article supplies only a publication date, the record labels it as such rather than inventing an event date.

Source metadata records title, publisher, source type/tier, retrieval time, publication date if known, and optional archive link if independently available and appropriate. No archive submissions or full-page screenshots are created automatically.

Stable IDs survive corrections. Exact entity/date/area/observation/action/quantity matches can associate sources while preserving provenance and returning the record for review. Similar names alone do not justify merging; unnamed or undated events are not automatically matched across publishers. Syndication is not independent corroboration. Prior versions remain in private audit history with change notes and hashes. Public suspended-record links show status without re-exposing the disputed claim.

## Fact and context separation

reported_fact and derived_context are different schema objects. Menu context, business format, establishment context, action grouping and geographic normalization are contextual classifications. They are not official findings. Automatically extracted contextual fields default to unknown or not reported. Non-default classifications require supporting evidence, an explicit allowed derivation method, confidence metadata and maintainer review. Menu and business-format classification cannot use names, cuisine guesses, surnames, neighbourhoods, religion or other social inference.

There is no demographic classification, ranking, compliance score, risk estimate or opinion analysis.

## Counts and interaction

Every summary and chart derives from public record rows. Each record contributes once to each chart, including unknown categories. Source count is the number of distinct canonical supporting URLs attached to published records; it is not all sources ever read. Establishment and area counts use distinct displayed names and do not claim a complete entity register.

Clicking a chart segment filters the evidence rows contributing to that count. A chart's count uses the complete published dataset; search and chart filters then intersect in the evidence table. Unknown values remain visible. Counts are subject to incomplete source coverage and must not be interpreted as prevalence, compliance, risk, wrongdoing or group behavior.

## Automated tools disclosure

Automated tools, including language models where enabled, may assist with extracting structured fields from publicly available source material. Language-model output is not treated as evidence. Published factual fields must remain linked to supporting source material and pass deterministic validation rules. The system does not use language models to determine guilt, legal liability, food safety, community identity, or whether an establishment committed wrongdoing.

Default extraction is deterministic. Live LLM calls require config enablement, --use-llm, credentials and a small call budget. The OpenAI-compatible interface accepts only a bounded verbatim observation candidate. Provider/model/task/version/validation provenance travels with the record. Remote API use may disclose source text to that provider; review its terms before enabling. VLM is disabled; no face recognition or local models are included.

## Limits and future work

This project cannot establish legal compliance, food safety, official totals or completeness. Coverage is affected by language, paywalls, discoverability and source availability. English and Bengali share data and chart logic; ?lang=bn selects static Bengali UI and policy summaries. Original quoted source text is never translated in place. Translations support accessibility, not evidentiary claims. Full policy text remains available in English. No runtime translation service, paid model, broad crawler or tracking is used.
