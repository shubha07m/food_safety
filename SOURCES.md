# Source policy, discovery and copyright

Discovery is intentionally broader than publication. Configured indexes, RSS/Atom feeds, URL/news sitemaps, curated URLs, an optional permitted search API, and maintainer-approved community leads may identify candidate URLs. Titles, snippets, search results, social posts, and discovery metadata are leads only. A candidate must still be retrieved from an allowed source and pass every evidence, schema, location, attribution, duplicate, and claim-safety gate.

The current bounded run can discover up to 80 unique URLs and process at most 20 new/due articles. New discovery and source revalidation have separate budgets. Exact-host request limits, persistent retry state, robots checks, response caps, redirect checks, and a host circuit breaker apply. Previously seen public sources are fetched once per run even when they support multiple records. There is no recursive crawl.

See the generated [source coverage report](reports/source_coverage.md) for measured yield. “Enabled” alone is not treated as success: the report records discovery mechanism, language, URLs seen, article fetch results, extraction yield, and controlled failure codes.

## Current acquisition status

- Times of India Kolkata, TV9 Bangla, Indian Express Bangla, and ABP Ananda have bounded same-domain index discovery. Their output varies and zero-yield runs are reported honestly.
- Business Today, UNI India, and Sangbad Pratidin currently use small curated URL sets.
- Telegraph India, Anandabazar, and News18 Bangla are manual-only after repeated normal retrieval failures or HTTP 403 responses. No bypass is attempted.
- Ei Samay remains a pilot; oversized or technically unsuitable responses fail closed.
- Zee 24 Ghanta is manual-only until a reliable bounded endpoint is validated.
- Normal checks of KMC failed at TLS negotiation; FSSAI pages returned no extractable article content. Official-source automation is therefore not claimed. Public official links may still be assessed manually.
- Public social-media posts are manual/community discovery leads unless they point to a durable underlying authority or publisher source. No login, private-group, session, or anti-bot scraping is permitted.

Source status is operational, not a credibility ranking. Tier A is an official public authority source. Tier B is an established identifiable news publisher. Tier C requires stronger corroboration and cannot independently pass automatic publication. Discovery-only sources never become evidence. Publisher-name difference alone does not establish independent corroboration; syndicated/republication relationships must be recorded and reviewed.

## Optional search discovery

The code includes a disabled Brave Search API adapter. It activates only when `search_provider: brave` is explicitly configured and `BRAVE_SEARCH_API_KEY` is supplied as a secret. Results are limited to already enabled exact publisher domains and remain leads. No search-result HTML is scraped, no key is committed, and normal operation does not require a provider. Maintainers must review the provider's current terms and pricing before enabling it.

## Community leads

The private-response Google Form is another discovery channel, never a publication channel. Export only reviewed responses to a CSV inside `data/tmp/`, then run:

```bash
python scripts/import_community_leads.py data/tmp/approved_form_responses.csv
```

The importer retains only a supported submission type and a safe public URL on an enabled automated host. It discards submitter/contact fields. The ignored local lead queue then enters the same bounded retrieval and validation pipeline. Corrections and licensing/compliance documents require their respective review workflows; they are not automatically published as inspection events.

## Evidence and rights

Retain the canonical URL, title, publisher, publication date when available, retrieval time, source/revision IDs, language, source relationship, hashes, and the minimum exact evidence/context spans. Individual evidence quotes are capped at 25 words and contexts at 60 words. These engineering caps are not a claim of legal immunity or universal copyright compliance.

Do not republish full articles, bypass paywalls, evade robots or access controls, upload pages to archive services, or download image collections. Optional archive links must already be available and legally/technically appropriate. Project code is MIT-licensed where stated; third-party articles, geographic material, trademarks, and other source content remain subject to their respective rights.

FSSAI website policy: https://fssai.gov.in/cms/website-policies.php
