# Methodology

Version 0.1.0. Private evaluation stage. Production starts with zero records. The preserved HTML prototype and synthetic test fixtures are not evidence.

## Unit of observation and scope

A record describes one source-supported reported event, with a date and area confirmed before publication. West Bengal is the geographic scope, initially emphasizing Kolkata and nearby areas. Maintainers must check geographic relevance. An establishment may be unnamed. Multiple establishments in one article require separate, correctly attributed evidence; the deterministic extractor never assigns an article-wide quantity or action to individual businesses.

Event date and publication date are distinct. Missing publication dates and quantities remain null. Dates must have explicit supporting ISO-date text in V1; sources using other date formats remain pending until a reviewed normalization adapter is implemented. This conservative limitation avoids invented dates.

## Processing and review

Configured curated article URLs → canonicalization → bounded robots-aware fetch → article-text extraction → candidate extraction → per-field evidence checks → sensitive-content checks → conservative association → source-policy checks → pending review or publication → aggregates → static site.

V1 has no recursive crawler or search-engine scraping. Robots failure, rate policies not yet supported, missing evidence, inaccessible sources, suspicious text and uncertain attribution fail closed. Full article bodies exist only in memory during processing. An ordinary update makes unnamed observation candidates and keeps them pending.

To publish, a maintainer prepares a schema-valid record and explicitly attests to reading the original context and checking every displayed field. The review command freshly retrieves every source, checks content hashes, exact short evidence spans and source policy. That human decision is recorded. Automated substring checks establish textual support, not meaning: negation, dates, entity attribution, source corrections and formal findings require human review.

A config switch and AUTO_PUBLISH environment gate both default false. Even when enabled, V1 candidate extraction cannot bypass the human-review requirement. Autonomous first publication is intentionally unavailable until a separately evaluated adapter and policy are introduced.

## Source tiers and statuses

A: official authority material. B: established identifiable news publishers with accessible articles. C: identifiable publications requiring stronger corroboration; V1 retains candidates for research but does not publish Tier C evidence. Discovery: snippets, aggregators, social media or other weak material; never fetched into the publication pipeline.

SOURCE VERIFIED: source existence, quoted support and context reviewed, not independent proof of the event. CROSS-SOURCE VERIFIED: independent publishers support the displayed observation; not proof of real-world truth. V1 review defaults to SOURCE VERIFIED even with multiple sources.

SINGLE SOURCE and PENDING REVIEW are not public acceptance states. SOURCE UPDATED, DISPUTED, SOURCE WITHDRAWN, SUPERSEDED and REJECTED are held out of public statistics. A failed later source check suspends the affected public record. Partial scans do not establish that every record was recently checked.

## Evidence, provenance and revisions

Every non-null fact has a supporting source URL and exact short quote in reported_fact.evidence. Quotes must sit inside a retained context span that matches fetched text. The text hash records which extracted version was reviewed, without retaining a full copyrighted article. Retained maximal evidence spans total at most 25 words per canonical source across the public dataset. This is a conservative engineering budget, not a legal safe harbour.

Source metadata records title, publisher, source type/tier, retrieval time, publication date if known, and optional archive link if independently available and appropriate. No archive submissions or full-page screenshots are created automatically.

Stable IDs survive corrections. Exact entity/date/area/observation/action/quantity matches can associate sources while preserving provenance and returning the record for review. Similar names alone do not justify merging; unnamed or undated events are not automatically matched across publishers. Syndication is not independent corroboration. Prior versions remain in private audit history with change notes and hashes. Public suspended-record links show status without re-exposing the disputed claim.

## Fact and context separation

reported_fact and derived_context are different schema objects. Menu category (veg, non-veg, both, unknown), business format (independent, chain/group, mall/food court, market/vendor, unknown), action grouping and geographic normalization are contextual classifications. They are not official findings. Non-default context requires linked source evidence, an explicit method, high confidence and human context review. No inference from names, presumed ownership identity or locality is permitted.

V1 leaves all automatically extracted context unknown/other. There is no demographic classification, ranking, compliance score, risk estimate or opinion analysis.

## Counts and interaction

Every summary and chart derives from public record rows. Each record contributes once to each chart, including unknown categories. Source count is the number of distinct canonical supporting URLs attached to published records; it is not all sources ever read. Establishment and area counts use distinct displayed names and do not claim a complete entity register.

Clicking a chart segment filters the evidence rows contributing to that count. A chart's count uses the complete published dataset; search and chart filters then intersect in the evidence table. Unknown values remain visible. Counts are subject to incomplete source coverage and must not be interpreted as prevalence, compliance, risk, wrongdoing or group behavior.

## Automated tools disclosure

Automated tools, including language models where enabled, may assist with extracting structured fields from publicly available source material. Language-model output is not treated as evidence. Published factual fields must remain linked to supporting source material and pass deterministic validation rules. The system does not use language models to determine guilt, legal liability, food safety, community identity, or whether an establishment committed wrongdoing.

Default extraction is deterministic. Live LLM calls require config enablement, --use-llm, credentials and a small call budget. The OpenAI-compatible interface accepts only a bounded verbatim observation candidate. Provider/model/task/version/validation provenance travels with the record. Remote API use may disclose source text to that provider; review its terms before enabling. VLM is disabled; no face recognition or local models are included.

## Limits and future work

This project cannot establish legal compliance, food safety, official totals or completeness. Coverage is affected by language, paywalls, discoverability and source availability. Bengali localization is planned; client strings are centralized. Future evaluated work includes date normalization, reviewed structured extraction adapters, stronger entity resolution, multi-language review and opt-in official-bulletin text extraction. No large crawls, models or automatic publication are part of V1.
