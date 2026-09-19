# Contributing

Work on `develop`; `main` is production and can receive bounded automated data
updates. Releases need owner approval and a merge commit, not a squash or history
rewrite. Reconcile newer production artifacts before release rather than overwriting
them with stale development data. See [maintenance](docs/MAINTAINER_GUIDE.md).

Read [Disclaimer](DISCLAIMER.md), [Methodology](METHODOLOGY.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md). Useful contributions include:

- Source verification for Puja listings, California community organizers and future
  regions; explicitly published venue/year evidence, not unsourced lists.
- Independent geographic verification with precision and provenance; never guessed
  coordinates or Gemini memory.
- Sourced Bengali/English aliases, readable UI and accessibility.
- OSM/open-data improvements and restaurant identity corrections. Follow OSM's own
  contribution policies; do not copy restricted provider content into OSM.
- West Bengal Food Safety evidence corrections, source rechecks and lifecycle review.

Puja, food discovery and Food Safety are separate datasets. A nearby business is not
inspected, recommended or safety-rated. Regional food-search links are not restaurant
records. An ID-only provider suggestion is not verified cross-provider identity.

Use public PRs for code and non-sensitive data proposals. Source/correction intake may
use the configured private-response Google Form or the controlled issue templates as
appropriate; never post private information, unsupported allegations, full copyrighted
articles or raw provider responses. Nothing submitted publishes automatically.

For source-backed data, include canonical URLs, source title/date where known,
retrieval time and minimal exact support. Preserve stable IDs and unknown values.
Puja additions require reviewed configuration. Normal Food Safety extraction can publish
after objective validation; complex corrections, semantic holds and derived context
retain explicit maintainer-review requirements. Syndicated copies are not independent
corroboration.

For code, use the project environment, focused changes and synthetic fixtures. Run
Ruff, Python/frontend tests, schema validation, deterministic build, public-output
verification and relevant browser smoke. Automated tests must not consume live provider
quota. Keep runtime caches and local environments ignored.

Repository controls include protected release workflow, required CI and scoped action
permissions; check actual current settings rather than assuming a document proves
them. Never put real keys into tracked map configuration or test fixtures. Ordinary
local map fallback is expected; use the isolated artifact for deliberate live tests.

Independent legal review remains outstanding. Contributions do not bypass publication
or source-rights boundaries.
