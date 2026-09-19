# Static deployment

Canonical site: https://foodsafety.nemoneek.com/

`main` is production; `develop` is implementation. Preserve the existing hosting
integration and reconcile newer scheduled production data before an owner-approved
merge commit. Do not deploy the repository root.

## Source and artifact

Tracked `site/` contains validated static assets and a blank `maps-config.json`.
The existing Node build copies it to ignored `dist/site/` and injects browser
configuration only into that deployment artifact:

~~~sh
node scripts/build_deployment.mjs && npx wrangler deploy --config dist/wrangler.json
~~~

The generated Wrangler file derives existing settings and points at the artifact.
The hosting build must independently receive `GOOGLE_MAPS_BROWSER_KEY`; Actions
environment values do not transfer to it. `REQUIRE_BROWSER_MAP_CONFIG=true` requires
configuration. Neither private operator key belongs in public output. No Python build,
provider discovery or snapshot download is needed in this deployment step.
[Browser setup and local artifact testing](BROWSER_MAP.md).

Actions validates source/data, stages an explicit generated-file allowlist and checks
an isolated artifact after the commit boundary. It does not deploy the site.
Release-triggered builds skip source/Gemini research; scheduled ingestion remains
bounded. The hosting integration observes `main`. Green GitHub CI alone does not
prove hosting deployment succeeded.

## Verification

~~~sh
python scripts/verify_public_output.py
python scripts/stage_generated.py
python scripts/verify_public_output.py --runtime --site dist/site
python scripts/check_deployment.py
~~~

Runtime verification needs the same environment used to build that artifact. Check
HTTPS and response policies on the live domain, then Kolkata/California, English/Bengali,
food handoffs, optional live map, Food Safety, record details and corrections.
Ordinary local `site/` serving deliberately uses the map fallback.

## Rollback and operations

Use existing deployment history for an approved rollback, followed by a reviewed revert
where needed. Never force-push public history as routine rollback. Pause research
refresh when accuracy requires it; source lifecycle corrections remain distinct from
UI deployment. Preserve stable record IDs and later production tombstones.

GitHub schedules are best-effort; watch failed runs and last-successful timestamps.
Public-repository inactivity can affect scheduling. Check current branch protections,
required checks and narrowly scoped bot permissions before release; no static document
attests to the live settings. [Maintainer procedure](MAINTAINER_GUIDE.md).
