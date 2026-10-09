# Visual asset provenance

## Social preview

- `site/assets/social-preview.svg`: existing project-authored vector layout;
  text updated for The Bengal FoodPath, Puja discovery and five-region scope.
- `site/assets/social-preview.png`: rendered from that SVG with the existing
  local browser-smoke screenshot process (`FOOD_UPDATE_SOCIAL_PREVIEW=1 node
  scripts/browser_smoke.mjs`, with the local static server running). No new artwork generation, external
  assets, Google imagery or credentials. Food Safety remains West Bengal-only.

## Current product screenshots

- `puja_preview.png` and `california_food_preview.png`: captured from the local
  static development release using `FOOD_UPDATE_PREVIEWS=1 node scripts/browser_smoke.mjs`.
- Updated: 2026-09-22; five-region selector, explicit Near Me control, named OSM food and regional search UI.
- Screenshots contain project UI, attributed OSM-derived facts and the maintainer's
  supplied hero artwork. No Google map imagery, browser chrome or runtime values.
- These are interface illustrations, not evidence of venue availability or endorsement.
- The older `readme_banner.svg` and `dashboard_preview.png` are historical assets;
  they are not the current README presentation.

## Puja hero

- Development source: `puja_hero_source.png`
- Website derivative: `../../site/assets/puja/puja_hero.webp`
- Added: 2026-09-16
- Provenance: supplied by the project maintainer for The Bengal FoodPath.
- Processing: resized to 1376 × 768 and encoded as WebP at quality 82; the
  composition was not generated or altered by Codex.

The image is used as seasonal presentation, not as evidence or source data.
Unless the rights holder states otherwise, do not assume this artwork is covered
by the repository's MIT software license or reuse it independently.
