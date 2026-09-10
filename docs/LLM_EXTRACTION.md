# Bounded structured extraction

The language model proposes structured candidate records from source documents. Candidates that satisfy all source-grounding, schema, semantic, and safety checks may be published automatically. Ambiguous or higher-risk cases are held for human review. Invalid evidence is rejected. Human review is an exception path, not a universal prerequisite.

## Current mode

`config/pipeline.yml`: `llm_enabled: true`, `llm_mode: shadow`, `publish_from_llm: false`. Deterministic publication continues. Missing `GEMINI_API_KEY` produces a separate diagnostic and no request. Disable with `LLM_ENABLED=false`, `llm_enabled: false`, or `update --no-llm`.

The implemented future setting is `llm_mode: guarded` plus `publish_from_llm: true`; existing `auto_publish` and `AUTO_PUBLISH=true` are also required. Adding a key does not enable model publication. Shadow mode wins even if publish_from_llm is true. Development stays on develop; main/Cloudflare remain production.

Limits: five calls/run, 24,000 input passage characters/article, 4,096 output tokens, 12 candidates/article, 128 KiB response, 20-second timeout, no automatic model retry. Oversized input reports input_incomplete, never silent truncation. Truncated/refused/malformed responses cannot publish. A US$0.05/run conservative list-price reservation uses UTF-8 input bytes and maximum output tokens. Actual token-based estimates are separate; provider billing/quota controls remain necessary. No automatic model fallback or hidden paid provider.

Cache identity includes source ID/revision, parser, schema, task, prompt, provider, configured model and output limits; returned model version and call time are recorded. Cached proposals are revalidated on use. Server-side model aliases may change: use a new explicit model/task version or remove the specific private cache entry when intentionally reevaluating. Cached responses are not independent model runs.

## Provisional adapter, not a benchmark-proven winner

One provider-neutral `StructuredExtractor.extract(document_revision, candidate_schema, task_version, limits)` interface has a Gemini REST adapter using existing httpx/Pydantic. Generated JSON Schema is sent through responseJsonSchema and revalidated locally. No SDK, Instructor, local weights or dependency installation. The older OpenAI-compatible observation helper remains for compatibility, not as an alternative ingestion publisher.

The provisional configuration is **gemini-2.5-flash-lite**, selected for documented free access, structured JSON support and low paid list rates—not measured Bengali superiority. Gemini 2.5 Flash is a possible comparison, but neither was live-benchmarked here. No credentials were available and no calls were made. English/Bengali/mixed-language fixtures test the application, not the model's language quality.

Official documentation checked 2026-09-09: [model catalog](https://ai.google.dev/gemini-api/docs/models), [generation/JSON Schema configuration](https://ai.google.dev/api/generate-content), [pricing/data use](https://ai.google.dev/gemini-api/docs/pricing). Listed Flash-Lite text rates are $0.10/M input and $0.40/M output tokens; availability/rates can change. Free-tier data use includes product improvement: send only permitted public source text, never private notes/form responses. Account billing configuration determines whether calls are free.

Owner setup: review provider terms/data use, obtain an API key from Google AI Studio, choose eligible free access or explicitly configure billing limits, then set `GEMINI_API_KEY` in the local process environment. No dotenv loader is assumed. After an approved merge, scheduled use can read an Actions secret of the same name. Never put keys in frontend files, command arguments, Git, manifests or issues. No Cloudflare configuration is needed.

## Validation and autonomy

1. Freeze ordered original passages, identified as P001/P002 within a revision.
2. Validate bounded envelopes and individual siblings independently; the model cannot set publication state, reviewer attestations or source tier.
3. Resolve quotes exactly, with NFC/whitespace fallback mapped back to original code-point offsets. Ambiguous repeated spans require more specific evidence. No fuzzy or translated proof.
4. Omit unsupported optional quantities; reject unsupported core facts. Never remove a negation or material qualification to salvage a record.
5. Independently reconstruct scope/entity/area/authority/action relationships through the tested explicit-inspection grammar. Interpreted dates, unclear quantities, corrections, negation and relationship suggestions are exceptions. No model-confidence score or critic model.
6. Guarded admission rechecks revision and original locator, source date/context, duplicate ambiguity and the normal publication validator. No human attestation is invented. Model/cache/queue failures cannot change source lifecycle states.

The narrow semantic grammar is the current autonomy ceiling. Model recall beyond it may improve review, but is not automatically proven. Extend supported syntax through labeled cases and tests, not relaxed evidence matching. Article co-occurrence is not event equivalence; aggregate counts never create fabricated establishments.

## Private evaluation

```bash
python -m food_safety.cli llm-prepare --max-articles 30
python -m food_safety.cli llm-evaluate --max-articles 30
# Only after provider setup; explicit bounded inference:
python -m food_safety.cli llm-evaluate --max-articles 30 --use-llm
```

Preparation uses known configured URLs, five articles/host maximum, stopping a host after one failure. It reuses frozen articles; no crawling, publication or model calls. `.cache/llm_eval/` contains private corpus, unreviewed gold templates, responses, validation decisions and usage. Do not commit/upload these. Full source text is local-only and should be removed when no longer needed.

Review gold against complete articles; bind labels to revisions and split by underlying story, including syndicated copies. Templates are not gold. Label relevance, scopes, raw fields, evidence passages, exclusions and ambiguity; record actual reviewer time. Adjudicate alternate valid representations. Do not infer reviewer approval from existing partial records.

The current scorer reports per-article exact record/field precision/recall for exhaustive reviewed labels, plus language/publisher, status, latency and token/list-cost usage. Missing gold/model results are null, not perfect/zero scores. Raw model hallucination, detailed association/date/scope and reviewer-effort metrics still need an adjudicated pass; not all are automated scores. Fixture tests are not empirical accuracy measurements.

Guarded exception decisions use private `queue/`. Scheduled runner files disappear when the job ends; local evaluation is durable for this stage. Before unattended guarded deployment, approve private exception retention rather than publishing raw candidates in Actions artifacts. This is an operational promotion gate, not mandatory human approval for clean records.

## Promotion threshold — not met yet

At least 30 fully reviewed real articles, growing toward 60 before broad quality claims. Use a Bengali-heavy corpus with English/mixed text, hard negatives, corrections, ambiguity, quantities, multiple businesses and aggregate operations. Hold out entire stories before prompt iteration.

For the automatic lane: zero fabricated evidence, zero unsupported admitted core facts, zero wrong entity/action/quantity/date associations in held-out tests; at least 98% admitted-field precision; no negative/corrected-case admission; all lifecycle/security regression tests pass. Demonstrate additional correctly supported records or reduced reviewer minutes against the deterministic baseline, within cost limits. Small samples do not establish a universal error rate. Resolve private exception retention before enabling scheduled guarded mode.

This pass makes no empirical model-winner or recall-gain claim. No chatbot, RAG, embeddings, database migration, training, VLM/OCR or critic is implemented.

Initial local preparation froze 17 source pages (10 Bengali, 7 English) from six publishers; a seventh publisher's response failed document checks. These are evaluation inputs, not 17 newly verified articles or gold labels. The deterministic adapter proposed three records. No templates are yet exhaustive reviewed gold, and no live model was run. The 30-article promotion threshold therefore remains unmet. Tests and private raw snapshots are not substitutes for that review.
