# Static deployment

Canonical site: https://foodpath.nemoneek.com/

## Hostname cutover (owner-controlled)

The legacy hostname is `https://foodsafety.nemoneek.com/`. Repository metadata
is prepared for the new origin; do not merge this migration until the owner has
attached the new custom domain to the existing Worker, verified DNS/TLS and added
the new origin to the browser Maps key's referrer allowlist (retain the old one).
No key, Worker identity, storage binding, workflow or deployment model changes.

Enforce HTTPS at Cloudflare for the new hostname. After the production merge and
successful deployment, permanently redirect the old hostname to the new one,
preserving the path and complete query string. Use a hostname-scoped Cloudflare
redirect rule, not application redirects; keep old DNS/TLS active. Verify region,
language, module, pandal and safety-event links. Update GitHub's homepage/About
manually. In Search Console verify both properties, submit the new sitemap and
use Change of Address only after redirects work; retain the old property and do
not use the removal tool. Retain redirects long-term. Roll back via normal Git
revert/release and dashboard redirect reversal, never reciprocal redirects.

## Canonical policy

This static app has one indexable application URL: `https://foodpath.nemoneek.com/`.
Food Safety (`module=safety`), Bengali (`lang=bn`), regions, selected Pujas and
safety record details remain shareable UI states, not separate SEO landing pages.
Every state receives the same initial canonical and Open Graph URL; JavaScript
does not change either. There are no SEO hreflang alternates for these consolidated
states; language navigation and accessible language labels remain unchanged.

Indexable support pages and generated full policy pages self-canonicalize to their
extensionless URLs, matching hosting normalization. Summaries and full policies
are distinct documents. The intentionally small sitemap lists only the app root;
it omits artificial lastmod dates. Support pages remain discoverable through links.
The map iframe stays noindex. Robots permits crawling canonical signals; it is not
an access-control mechanism. These changes do not prove resolution of specific
Search Console exclusions without inspecting the affected URLs.

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

The generated Wrangler file derives reviewed settings and points at the artifact.
It includes a small aggregate-only counter Worker, one SQLite-backed Durable Object,
and asset-first routing; only `/api/visits` explicitly invokes the Worker first.
No catalog, restaurant or source-fetch API is added. The deployment copies `worker/`
outside the public asset directory. See [counter setup and plan checks](VISIT_COUNTER.md).
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
HTTPS and response policies on the live domain, then all five regions, English/Bengali,
food handoffs, optional live map, Food Safety, record details and corrections.
Ordinary local `site/` serving deliberately uses the map fallback.

Before the first counter deployment, the owner must confirm the Workers plan and
SQLite Durable Object availability/quota. The `visits-v1` migration creates the
aggregate binding on an approved deployment; local development and `--dry-run` do
not provision it. Do not enable a paid plan merely for the counter. On Free, exhausted
allowances should fail the counter rather than create overage charges; static pages
must remain usable. On Paid, request/compute/storage overages are possible, including
abusive traffic. Source code caps writes, not all incoming requests or account billing.

## Rollback and operations

Use existing deployment history for an approved rollback, followed by a reviewed revert
where needed. Never force-push public history as routine rollback. Pause research
refresh when accuracy requires it; source lifecycle corrections remain distinct from
UI deployment. Preserve stable record IDs and later production tombstones.

GitHub schedules are best-effort; watch failed runs and last-successful timestamps.
Public-repository inactivity can affect scheduling. Check current branch protections,
required checks and narrowly scoped bot permissions before release; no static document
attests to the live settings. [Maintainer procedure](MAINTAINER_GUIDE.md).
