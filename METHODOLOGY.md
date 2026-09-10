# Methodology

Public beta at https://foodsafety.nemoneek.com/ . The repository contains an initial public-source sample. The preserved HTML prototype and synthetic test fixtures are not evidence.

## Coarse geographic context

Where an unambiguous reported area can be independently located, the tracker may show a reviewed OpenStreetMap reference coordinate with an explicit precision label. These are area anchors, not establishment addresses, inspection locations or evidence of geographic prevalence. Ambiguous or district-only areas remain unmapped.

## Unit of observation and scope

A record describes one source-supported reported event, with a date and area confirmed before publication. West Bengal is the geographic scope, initially emphasizing Kolkata and nearby areas. Geographic relevance must be established before publication. An establishment may be unnamed. Multiple establishments in one article require separate, correctly attributed evidence; an article-wide quantity or action is never assigned to individual businesses without explicit support.

Event date and publication date are distinct. Missing publication dates and quantities remain null. Event dates require explicit supporting date evidence; a source publication date may be retained separately when the event date is not established. This conservative limitation avoids invented dates.

## Processing and review

Bounded publisher indexes, feeds, configured sitemaps, curated URLs, optional permitted search API results and approved community leads → canonicalization → bounded robots-aware fetch → article-text extraction → LLM candidate extraction → per-field evidence checks → sensitive-content checks → duplicate/source-policy checks → publish or skip → aggregates → static site.

The pipeline has no recursive crawler or search-result HTML scraping. A run may discover up to 80 unique URLs and process at most 20 new/due articles (hard ceiling 30), with separate new-discovery and source-revalidation budgets. Discovery pages, feeds, sitemaps and search results are never evidence. New-record admission fails closed on retrieval failure, missing evidence, suspicious extracted fields or uncertain attribution. Existing records follow the bounded-continuity policy below. Article bodies exist only in memory during routine processing.

For normal new-article ingestion, one bounded multilingual language-model call converts ordered source passages into structured candidates. It may return multiple establishment or operation records, but aggregate quantities remain one operation and never manufacture establishment rows. Structured page metadata or an explicitly grounded event date supplies date provenance. Every candidate still needs exact per-field evidence, an accessible Tier A/B source, a valid source revision and schema, safe claims, and no duplicate. Missing values remain unknown. Publication date is not event date. Existing manual tooling remains available for corrections and legacy records, not as a prerequisite for model-extracted publication.

The configuration enables model extraction and automatic publication after validation; the scheduled workflow also sets AUTO_PUBLISH=true. Automatic records carry automatic_validation provenance, never a fabricated human-review attestation. Candidates that do not pass objective checks are skipped rather than placed in an LLM review queue. There is no promise that every article yields a record. Existing lifecycle review remains available for later corrections, disputes and source changes.

## Evidence lifecycle — version 2

Transport failure changes availability. Material uncertainty changes review status. Evidence failure changes publication eligibility. Prolonged unverifiability changes active visibility, not historical truth.

New records need accessible permitted sources, source identity, exact field evidence, date/location support, safe attribution and deduplication. Publication remains strict. The multilingual extractor proposes structure, while objective validators require grounded original-language evidence; Bengali original text is never replaced by translated evidence.

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

The language model proposes structured candidate records from source documents. Candidates that satisfy schema, exact evidence-grounding, source, duplicate, safety and publication checks may be published automatically. Ambiguous or unsupported candidates are skipped. Unsupported optional quantities may be omitted, but missing required event, entity, attribution or action support cannot be dropped to salvage a claim.

The LLM is the normal interpretation layer for new articles. Downstream code verifies structure, source identity/revision, verbatim evidence, shared evidence references for required fields, dates, permissions, safety and duplicates; it does not require agreement from the retired phrase grammar. Missing credentials or model failure skips new extraction without changing existing records or source lifecycle state.

Frozen source revisions preserve ordered passages and original text. The application resolves model-proposed quotes using exact, NFC Unicode or whitespace-normalized matching, mapping offsets back to original text. No fuzzy match or translation proves evidence. Original and normalized values remain separate. Explicit correction/withdrawal markers, dates, structural field-to-evidence association, duplicates and source permissions are checked independently. A publication date is not silently converted into an event date. Relationship suggestions never create public claims by themselves.

Provider/model/task/schema versions, source revision, usage and validation decisions are retained privately; any model-assisted published record carries provenance and a short original evidence locator. There is no website chatbot, public Q&A, model training, fine-tuning, critic model, VLM, OCR, face recognition or local model installation. Remote extraction sends bounded public source text to the configured provider; review its terms and data-use settings first. Model failure is separate from source failure and cannot suspend a record. Technical limits and diagnostic commands are documented in docs/LLM_EXTRACTION.md.

## Limits and future work

This project cannot establish legal compliance, food safety, official totals or completeness. Coverage is affected by language, paywalls, discoverability and source availability. English and Bengali share data and chart logic; ?lang=bn selects static Bengali UI and policy summaries. Original quoted source text is never translated in place. Translations support accessibility, not evidentiary claims. Full policy text remains available in English. There is no runtime translation service, broad crawler or visitor tracking. Configured hosted extraction may incur bounded provider charges; free access must not be assumed for every account.
