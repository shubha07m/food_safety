# West Bengal Food Safety Evidence Tracker

Independent public-source research. **Not a government database. Inclusion is not a finding of wrongdoing.**

This private evaluation project structures publicly reported food-safety events in West Bengal, initially emphasizing Kolkata and nearby areas. Every published fact carries source evidence; every chart opens its contributing records. Production data starts empty. The preserved [design prototype](Wb-Food-Safety-Tracker.html) is illustrative and is not a source dataset.

Read [Disclaimer](DISCLAIMER.md), [Methodology](METHODOLOGY.md), [Corrections](CORRECTIONS.md) and [Privacy](PRIVACY.md) before using the data. The policy wording is a draft, not legal advice or legal immunity. India-qualified counsel should review it before broad public launch.

## Run locally

From `/Users/shubh/food_safety`, the local conda environment named `food` lives at `.conda/envs/food`. Activate it by path to avoid modifying conda's global environment registry:

```bash
conda activate /Users/shubh/food_safety/.conda/envs/food
python -m food_safety.cli build
python -m http.server 8000 --bind 127.0.0.1 --directory site
```

Open http://127.0.0.1:8000. Serve only `site/`, never the repository root. A rebuild copies validated public data and policy pages into the site. Local serving requires no cloud account, Node packages, API keys or external scripts.

For a clean checkout, run `bash scripts/setup_food.sh` first. It creates/reuses the local food environment with Python 3.12 and installs the pinned dependencies. All environment, cache and temporary paths are inside the checkout. No base conda, global Python, shell profiles or global npm packages are modified. Existing global environments are not reused or changed. The separately supplied environment.yml describes the same environment for CI/tooling; the setup script also installs the full transitive dependency lock.

## Maintainer commands

```bash
python -m food_safety.cli validate
python -m food_safety.cli update --max-articles 3
python -m food_safety.cli pending
ruff check .
python -m pytest -q --basetemp=.cache/pytest
node --test tests/site_data.test.mjs
```

An optional local browser smoke test is available as `node scripts/browser_smoke.mjs` with the loopback server running. It uses the already-installed macOS Chrome, a project-local profile and in-memory synthetic records; it does not install a browser or alter production data. Screenshots stay in ignored `.cache/browser-smoke/`. This is not a CI browser farm.

The initial source policies are disabled with no seed articles: the update command performs no source requests. It records that no sources were enabled and does not invent a successful scan. Add only a small number of individually selected URLs after checking source policy, relevance and access. There is no broad crawler. Network requests are bounded at 10 articles, 5 articles per source, 15-second socket timeout, 512 KiB per response and 3 redirects; the default CLI scan requests at most 3 articles. DNS resolution is subject to OS behavior, as described in SECURITY.md.

`data/events.json` holds published records; `pending.json` holds schema-valid review candidates; `rejected.json` holds content-free rejection identifiers/reasons. Only public records, aggregates, CSV, status and minimal suspended-record notices are copied to the site. `data/history/` is a private audit archive. Meaningful revisions preserve IDs, notes and previous-version hashes. A later failed or changed source check suspends affected published records. A failed scan returns a nonzero exit status without pretending freshness.

To publish a candidate, edit a review copy inside `data/tmp/`, then run the explicit `review` command documented in [CORRECTIONS.md](CORRECTIONS.md). It freshly retrieves all supporting sources and requires source-context and field-support attestations. Read negation, dates, location, attribution and subsequent corrections in context. Never promote demo records. V1's exact-evidence rules deliberately leave ambiguous dates and attribution pending.

## Architecture

Small Python package → bounded configured-source retrieval → exact evidence validation → sensitive/claim-safety checks → conservative association → review queues → deterministic public data → static HTML/CSS/JavaScript.

The frontend uses no framework, third-party chart library, CDN, external font or runtime API. Native accessible chart buttons show a proportional bar and filter the evidence table. All metrics derive from JSON rows. Dynamic copy is centralized in `site/strings.mjs` to support later Bengali localization. Stable `?event=WBFS-…` links show source spans, field support, context, status, model provenance and history.

## LLM / VLM

Default: `no_llm`. The optional OpenAI-compatible API extractor is vendor-independent and only returns a short verbatim observation candidate. To enable live calls, explicitly set `llm_enabled: true`, provide the empty-placeholder variables described in `.env.example`, and pass `--use-llm --max-llm-calls 1`. No `.env` file is automatically loaded; export variables deliberately in your session or inject secrets through approved tooling. Keep keys out of Git and frontend assets.

The input is capped at 12,000 characters, output at 250 tokens and 32 KiB, with at most 5 calls per run. Calls are not retried automatically. Model output is untrusted, must match evidence and remains subject to context review. CI mocks all calls and has no model secrets. VLM is an explicit disabled interface; no OCR collections, image models, weights or face recognition are installed.

## Automation and deployment

CI runs lint, fixtures, browser-data logic, schema validation, static build and a dependency audit in conda `food`. Action versions are pinned to commit SHAs; credentials are not persisted by checkout. Pull requests never run a crawler or access paid API keys.

The source-update workflow is manual-only. A six-hour schedule is present as commented configuration. `auto_publish: false` and `AUTO_PUBLISH=false` are the defaults. The workflow produces review artifacts with seven-day retention; it does not commit or deploy. Enabling these switches alone cannot bypass V1 human review. A production automation adapter and publication process need separate review.

Deployment is prepared for [Cloudflare Pages or GitHub Pages](docs/DEPLOYMENT.md) but is not enabled. The repository must remain private during evaluation. Before changing visibility, inspect pending/history content and Issues: private audit material is not suitable for automatic public release. Establish a publicly accessible correction channel and obtain legal review before public promotion.

## Repository and contributions

See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), [DATA_DICTIONARY.md](DATA_DICTIONARY.md), [SOURCES.md](SOURCES.md), [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) and [CHANGELOG.md](CHANGELOG.md).

If private repository creation is unavailable, after authenticating GitHub run:

```bash
gh repo create food_safety --private --source=. --remote=origin
git push -u origin main
```

No public deployment is implied by a push. Configure the verified GitHub repository URL in `config/pipeline.yml` so correction/source forms link to the correct repository. Private Issues are available only to collaborators.

MIT applies to project-authored code/documentation; it does not relicense third-party article content. No blanket ownership/licensing claim is made over source facts or the compiled data. Preserve attribution and interpretation context when sharing.

## Next research step

Manually validate a very small set of real West Bengal sources, exercise review and corrections, then assess publication with India-qualified counsel before enabling any schedule or public release. Larger ingestion, normalized date adapters, Bengali content, wider entity resolution and optional official-bulletin extraction are future work, not part of the initial run.
