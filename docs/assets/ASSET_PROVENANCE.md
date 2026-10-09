# Visual asset provenance

## Optional Dhaak recording

- File: `site/assets/puja/dhaak.mp3` (repository-root relative).
- Added: 2026-10-09; supplied by the project maintainer, unchanged.
- Per the maintainer, generated specifically for this project using Google Gemini
  audio generation / their generation workflow. No generation API is used by the site.
- Intended use: optional, explicitly user-started Puja ambience; looping stops on
  user request, navigation away, or when the page is hidden. No autoplay.
- MP3, stereo, 44.1 kHz, 192 kbps; approximately 60.45 seconds; 1,456,860 bytes.
- SHA-256: `3739d5a86272f64058a9bd146df345e3fb1ad6f5ecfb8b138c382e8394f5dfa0`.
- Rights/provenance established here are project-generated / user-supplied and
  intentionally supplied for this use. No separate license or generation receipt
  was supplied; this is not a claim of exclusive ownership, CC licensing, or MIT
  coverage of the recording.

## Optional Dhaak animation

- File: `site/assets/puja/dhaak-playing.mp4` (repository-root relative).
- Added: 2026-10-09; supplied by the maintainer as a Google Gemini-generated
  decorative Dhaak animation. Original bytes retained; no re-encoding or audio
  stripping (ffmpeg unavailable locally).
- SHA-256: `2ddce497a3fa9a0a704173e9e06008a307ab4355dbfaf43ecb863147216785cb`.
- Browser-decoded metadata: 1280 × 720, 10.005 seconds; 1,791,941 bytes.
- The original contains audio, but the site always mutes it in markup and JavaScript,
  also setting video volume to zero. Only `dhaak.mp3` supplies audible playback.
- Loads only after explicitly starting the Dhaak sound; loops while sound plays,
  resets on stop/navigation, and stays hidden/paused for reduced-motion preferences.
- Provenance is project-generated / user-supplied for this use. No separate license
  or generation receipt supplied; no claim of CC licensing or MIT media coverage.

## Social preview

- `site/assets/social-preview.svg`: existing project-authored vector layout;
  text updated for FoodPath, Puja discovery and five-region scope.
- `site/assets/social-preview.png`: rendered from that SVG with the existing
  local browser-smoke screenshot process (`FOOD_UPDATE_SOCIAL_PREVIEW=1 node
  scripts/browser_smoke.mjs`, with the local static server running). No new artwork generation, external
  assets, Google imagery or credentials. Food Safety remains West Bengal-only.

## Current product screenshots

- `puja_preview.png`, `california_food_preview.png` and `dashboard_preview.png`: captured from the local
  static development release using `FOOD_UPDATE_PREVIEWS=1 node scripts/browser_smoke.mjs`.
- Updated for the final FoodPath brand: five-region selector, explicit Near Me control,
  named OSM food and regional search UI. The dashboard preview shows the separate
  West Bengal Food Safety Evidence module with real published data.
- Screenshots contain project UI, attributed OSM-derived facts and the maintainer's
  supplied hero artwork. No Google map imagery, browser chrome or runtime values.
- These are interface illustrations, not evidence of venue availability or endorsement.
- `readme_banner.svg` is an alternative project-authored vector banner, updated
  to FoodPath. The README uses the current product screenshots above.

## Puja hero

- Development source: `puja_hero_source.png`
- Website derivative: `../../site/assets/puja/puja_hero.webp`
- Added: 2026-09-16
- Provenance: supplied by the project maintainer for FoodPath.
- Processing: resized to 1376 × 768 and encoded as WebP at quality 82; the
  composition was not generated or altered by Codex.

The image is used as seasonal presentation, not as evidence or source data.
Unless the rights holder states otherwise, do not assume this artwork is covered
by the repository's MIT software license or reuse it independently.
