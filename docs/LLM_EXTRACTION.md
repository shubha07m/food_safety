# Structured extraction

The language model proposes structured candidate records from fetched source documents. Python validates schema, evidence spans, meaning, safety and duplicates. Fully validated candidates may publish automatically; ambiguous candidates enter a private exception queue and unsupported candidates are rejected. Human review is only for exceptions.

## Configuration

```yaml
llm_enabled: true
publish_from_llm: true
llm_provider: gemini
llm_model: gemini-3.5-flash-lite
```

Set `LLM_ENABLED=false` or use `update --no-llm` to run deterministic extraction only. Missing `GEMINI_API_KEY`, model timeouts, refusals and malformed output do not affect source lifecycle or existing records. The normal update command invokes the model automatically when credentials are present.

Limits are five calls/run, 24,000 passage characters/article, 4,096 output tokens, 12 candidates/article, 128 KiB response and a 20-second timeout. Revision/model/task/schema/prompt-aware caching prevents resending unchanged source revisions. Cache entries are revalidated before use. No automatic provider retry or fallback is hidden.

## Evidence boundary

The model sees ordered frozen passages and may return multiple scoped candidates with verbatim quotes and passage IDs. The application resolves quotes exactly, with NFC and whitespace-normalized fallback mapped to the original text. Fuzzy similarity and translation are never evidence. Model output cannot set publication state, source tier or review attestations. Optional unsupported fields may be omitted; unsupported core meaning is reviewed or rejected. Aggregate counts remain operation records and never fabricate establishments.

Article text is untrusted data. The prompt treats instructions inside it as data, uses no tools, and cannot alter destinations or policy. Published model-assisted records carry source revision, evidence locator and model provenance. There is no chatbot, public Q&A, training, fine-tuning, VLM/OCR or vector database.

## Provider and cost

The adapter uses a provider-neutral `StructuredExtractor` protocol and Gemini's REST `generateContent` endpoint with JSON Schema response configuration. It uses only existing httpx/Pydantic dependencies. The configured model is provisional; no live model comparison is claimed. Provider errors are sanitized to HTTP status/provider code/message without credentials or source bodies. The list-price estimate is recorded from returned usage; no separate estimated-spend gate blocks calls. Provider quotas and billing limits remain the maintainer's responsibility.

## Optional diagnostics

`python -m food_safety.cli llm-test --max-articles 3 --use-llm` runs against the ignored local corpus when available. It is diagnostic only, does not gate publication and does not require labels or a benchmark. The local corpus and responses under `.cache/llm_eval/` are private and must never be committed or uploaded. No evaluation corpus is required for normal ingestion.

## Owner setup

Export `GEMINI_API_KEY` only in the local process, or add it as a GitHub Actions repository secret before enabling model calls in scheduled production. Never commit it, pass it in URLs, or expose it to the static site. Review Google's current terms, data-use settings, pricing and free-tier eligibility before sending public source passages. No Cloudflare secret or frontend key is needed.
