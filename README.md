# West Bengal Food Safety Evidence Tracker

Independent public-source research. **Not a government database. Inclusion is not a finding of wrongdoing.**

**Public-beta release candidate.** No deployment is enabled by this repository.

This private evaluation project structures publicly reported food-safety events in West Bengal, initially emphasizing Kolkata and nearby areas. Every published fact carries source evidence; every chart opens its contributing records. The current dataset is a reviewed initial real-source sample. The preserved [design prototype](Wb-Food-Safety-Tracker.html) is illustrative and is not a source dataset.

Read [Disclaimer](DISCLAIMER.md), [Methodology](METHODOLOGY.md), [Corrections](CORRECTIONS.md) and [Privacy](PRIVACY.md) before using the data. The policy wording is a draft, not legal advice or legal immunity. India-qualified counsel should review it before broad public launch.

## Run locally

Clone the repository, enter it, and create or reuse the repository-local environment:

```bash
git clone <repository-url>
cd food_safety
bash scripts/setup_food.sh
conda activate "$(pwd)/.conda/envs/food"
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

Source policies contain a small reviewed whitelist of seed articles. The update command remains bounded and fail-closed; it is not a broad crawler and cannot publish a new record without explicit review. Network requests are bounded at 10 articles, 5 articles per source, 15-second socket timeout, 512 KiB per response and 3 redirects; the default CLI scan requests at most 3 articles. DNS resolution is subject to OS behavior, as described in SECURITY.md.

`data/events.json` holds published records; `pending.json` holds schema-valid review candidates; `rejected.json` holds content-free rejection identifiers/reasons. Only public records, aggregates, CSV, status and minimal suspended-record notices are copied to the site. `data/history/` is a private audit archive. Meaningful revisions preserve IDs, notes and previous-version hashes. A later failed or changed source check suspends affected published records. A failed scan returns a nonzero exit status without pretending freshness.

To publish a candidate, edit a review copy inside `data/tmp/`, then run the explicit `review` command documented in [CORRECTIONS.md](CORRECTIONS.md). It freshly retrieves all supporting sources and requires source-context and field-support attestations. Read negation, dates, location, attribution and subsequent corrections in context. Never promote demo records. Exact-evidence rules deliberately leave ambiguous dates and attribution pending.

## Architecture

Small Python package → bounded configured-source retrieval → exact evidence validation → sensitive/claim-safety checks → conservative association → review queues → deterministic public data → static HTML/CSS/JavaScript.

The frontend uses no framework, third-party chart library, CDN, external font or runtime API. Native SVG charts, completeness panels and combined filters all derive from JSON rows and reveal their contributing evidence. Dynamic copy is centralized in `site/strings.mjs` where practical to support later Bengali localization. Stable `?event=WBFS-…` links separate reported facts, derived context, source evidence, verification, history and disclaimer.

## LLM / VLM

Default: `no_llm`. The optional OpenAI-compatible API extractor is vendor-independent and only returns a short verbatim observation candidate. To enable live calls, explicitly set `llm_enabled: true`, provide the empty-placeholder variables described in `.env.example`, and pass `--use-llm --max-llm-calls 1`. No `.env` file is automatically loaded; export variables deliberately in your session or inject secrets through approved tooling. Keep keys out of Git and frontend assets.

The input is capped at 12,000 characters, output at 250 tokens and 32 KiB, with at most 5 calls per run. Calls are not retried automatically. Model output is untrusted, must match evidence and remains subject to context review. CI mocks all calls and has no model secrets. VLM is an explicit disabled interface; no OCR collections, image models, weights or face recognition are installed.

## Automation and deployment

CI runs lint, fixtures, browser-data logic, schema validation, static build and a dependency audit in conda `food`. Action versions are pinned to commit SHAs; credentials are not persisted by checkout. Pull requests never run a crawler or access paid API keys.

The source-update workflow supports maintainer-only manual dispatch and a bounded six-hour schedule. `auto_publish: false` and `AUTO_PUBLISH=false` are the defaults. The workflow produces review artifacts with seven-day retention; it does not commit or deploy. These switches cannot bypass human review.

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

The release candidate contains a reviewed initial real-source sample. The next research stage focuses on source diversification and independent cross-source verification. Before public promotion, complete [the public release checklist](docs/PUBLIC_RELEASE_CHECKLIST.md) and run `scripts/release_public_beta.sh --confirm-public-release`; it validates but does not deploy unless the explicit Cloudflare option is used.
