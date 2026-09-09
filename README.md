# The Bengal FoodPath

Independent food-information research for West Bengal.

Current module: **Food Safety & Inspection Evidence** (West Bengal Food Safety Evidence Tracker).

This `develop` branch contains Phase 1 changes awaiting owner approval. The live site continues to deploy production `main`; branch data is not a claim about current production totals.

![West Bengal Food Safety Evidence Tracker — Public Beta](docs/assets/readme_banner.svg)

[![CI](https://github.com/shubha07m/food_safety/actions/workflows/ci.yml/badge.svg)](https://github.com/shubha07m/food_safety/actions/workflows/ci.yml)
**PUBLIC BETA · Python 3.12 · Static site · Cloudflare · MIT code · No tracking**

> Independent public-source research. **Not a government database. Inclusion is not a finding of wrongdoing.** Source verification means the cited source supports the displayed statement; it does not mean the project independently established the event as fact.

### [Explore the live tracker →](https://foodsafety.nemoneek.com/)

[বাংলায় দেখুন](https://foodsafety.nemoneek.com/?lang=bn) · [Methodology](METHODOLOGY.md) · [Disclaimer](DISCLAIMER.md) · [Data](https://foodsafety.nemoneek.com/data.html) · [Corrections](https://foodsafety.nemoneek.com/corrections.html) · [Contribute](CONTRIBUTING.md)

## What this is

A public-interest, educational and academic data-research project organizing publicly reported food-safety inspection events in West Bengal, initially Kolkata and nearby areas. Every published fact links to source evidence; every chart reveals the records behind its count.

This is not a blacklist, safety rating, official total, accusation platform or opinion-building project. It does not infer social/community identity or recommend patronizing or avoiding any business. Unknown information is shown, not guessed.

> ### 🤝 Help keep the tracker useful
>
> Volunteer maintainers are welcome for source review, Bengali/English coverage, data validation and open-data tooling. Evidence and safety standards apply to every contribution.
>
> **[Volunteer / Contribute →](CONTRIBUTING.md)** · No personal information is collected on this website.

## Dashboard preview

![Current dashboard: evidence metrics, geographic context and interactive charts](docs/assets/dashboard_preview.png)

Native SVG charts, source-linked records, combined filters, field completeness and missingness. The local West Bengal basemap uses coarse reviewed area anchors—not establishment addresses, incident density or risk.

## How it works

![Public sources → bounded retrieval → evidence and safety validation → structured records → static Cloudflare dashboard](docs/assets/pipeline.svg)

Public sources → bounded retrieval → exact evidence validation → safety checks and deduplication → structured record → interactive dashboard. Failed or ambiguous candidates do not become public records.

## Current coverage

The live dashboard computes its own totals from the [published JSON](https://foodsafety.nemoneek.com/data/events.json), with a matching [CSV export](https://foodsafety.nemoneek.com/data/events.csv). The initial sample is small and concentrated in a few publishers. Cross-source verification and contextual coverage remain limited. See [dataset quality](reports/v2_dataset_quality_report.md); its dated snapshot is not a live total.

Counts describe indexed reporting, **not prevalence, compliance, authority activity or wrongdoing**. Prototype values and test fixtures never enter production data.

## Automatic updates

**Refresh Food Safety Data** is scheduled approximately every two hours (`17 */2 * * *`) and can be run manually in GitHub Actions. Schedules are best-effort, not a freshness guarantee.

The workflow checks up to two configured discovery pages and six articles per run, reserving capacity for discovery and maintenance. New English/Bengali candidates require explicit supported inspection statements and all source, schema and safety gates. Ambiguous new records never publish. Previously published records receive dated access warnings for technical failures, not automatic evidence-failure suspensions. Semantic uncertainty leaves active analytics; 30 days without adequate revalidation leads to an unverifiable archive. Restoration preserves first-publication history. See [the detailed lifecycle](METHODOLOGY.md).

Public metrics distinguish Active, Ever published, warning and non-active states. These overlap and must not be added together. Private-response community intake is prepared through a configurable Google Form; no fake form URL or community queue count is displayed. A URL-only **Licensing & Compliance Documents** schema is a manually reviewed pilot with no published documents or quality endorsements. Language, source/revision IDs and field support prepare future research without adding AI, embeddings or a database.

Only approved public artifacts are committed to `main`; Cloudflare Git integration redeploys `site/`. No change means no empty commit. The workflow has no push trigger, so its generated commits cannot recursively start another source scan. Failed scans never advance the last-successful timestamp. Maintainers periodically audit a few new records.

Ordinary visitors have no refresh endpoint. Maintainers use **Actions → Refresh Food Safety Data → Run workflow**. [Short maintainer guide](docs/MAINTAINER_GUIDE.md).

## Evidence standards

`reported_fact` and `derived_context` are structurally separate. Exact short source spans support factual fields. Non-default contextual categories need evidence, method, confidence and maintainer review. `SOURCE VERIFIED` is about source support, not independently proven truth. Automatic validation has explicit provenance and never impersonates human review.

[Data dictionary](DATA_DICTIONARY.md) · [Source policy](SOURCES.md) · [Methodology](METHODOLOGY.md) · [Corrections](CORRECTIONS.md)

## Bengali support

Use **EN | বাংলা** or [`?lang=bn`](https://foodsafety.nemoneek.com/?lang=bn). Navigation, principal dashboard labels, charts, filters and policy summaries have static Bengali translations. Full policies are also available in English. The original English/Bengali source quotations remain unchanged and clearly labeled; UI translations are not evidence. No translation API, external font or tracking cookie is used.

Narrow Bengali ingestion now recognizes explicit authority/location/inspection constructions. It is not general Bengali language understanding: negation, ambiguous entities and unsupported structures remain pending. Discovery is bounded and publisher access restrictions are respected.

© 2026 Shubhabrata Mukherjee · The Bengal FoodPath. Independent public-interest data project. Project code is MIT-licensed where stated. Third-party content and trademarks remain subject to their respective rights.

Repository publication still requires the separate [historical privacy cleanup](docs/PUBLIC_REPOSITORY_AUDIT.md). This task does not change repository visibility.

## Run locally

```bash
git clone https://github.com/shubha07m/food_safety.git
cd food_safety
bash scripts/setup_food.sh
conda activate "$(pwd)/.conda/envs/food"
python -m food_safety.cli build
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

An existing local `food` environment can be reused. Python execution and dependencies stay in that environment. For an explicitly bounded local refresh: `AUTO_PUBLISH=true python -m food_safety.cli update --max-articles 3`. This may suspend unavailable source records; inspect the resulting diff.

## Architecture

| Component | Responsibility |
| --- | --- |
| `src/food_safety/` | Bounded retrieval, schemas, evidence validation, publication, exports |
| `config/` | Explicit source whitelist and hard request limits |
| `data/events.json` | Versioned approved research dataset |
| `site/` | Only public deployment output; native JS/SVG, local assets |
| `tests/` | Synthetic deterministic regression fixtures; no paid APIs |
| `.github/workflows/` | CI and bounded two-hour refresh |

Private pending/rejected queues, local article downloads, source snapshots and browser profiles are excluded from future commits. Minimal suspension tombstones preserve stable record status without republishing held claims. Historical Git content must be audited separately before changing repository visibility.

## Security and privacy

No public database, write API, accounts, comments, uploads, ad trackers, analytics or runtime third-party scripts. HTTPS, CSP, framing restrictions, safe link rendering, SSRF-aware retrieval and response caps remain in place. The map is locally bundled, with [attribution](site/assets/BASEMAP_LICENSE.md). Hosting providers may process operational logs under their own policies.

[Security](SECURITY.md) · [Privacy](PRIVACY.md) · [Deployment](docs/DEPLOYMENT.md) · [Public repository audit](docs/PUBLIC_REPOSITORY_AUDIT.md)

## Validate changes

```bash
ruff check .
pytest --basetemp=.cache/pytest
node --test tests/*.test.mjs
python -m food_safety.cli validate
python -m food_safety.cli build
python scripts/verify_public_output.py
```

The optional browser smoke uses an already-installed Chrome; no browser bundle is downloaded. Paid LLM/VLM calls remain disabled. Source submissions and Issues never publish automatically.

With the local server running, `node scripts/browser_smoke.mjs` checks the real and
synthetic UI without modifying public assets. Set `FOOD_UPDATE_PREVIEWS=1` for an
explicit refresh of the small README screenshot and social preview PNG.

## Contributing and volunteer maintainers

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Suggest a public source, request a correction, help audit evidence, improve Bengali wording or maintain the tooling. Controlled GitHub Issue Forms become publicly accessible when the maintainer makes the repository public. Until then, access requires a repository invitation.

## Disclaimer and licensing

**Project policy wording is not legal advice. Independent legal review has not been completed.** This project does not promise legal immunity. Preserve source links and interpretation notices when sharing; third-party commentary does not represent the project. See the full [disclaimer](DISCLAIMER.md).

Code is [MIT licensed](LICENSE). Third-party news content and geographic data are not relicensed by that license. Evidence excerpts retain their original rights; research data reuse must preserve attribution, limitations and applicable third-party rights.
