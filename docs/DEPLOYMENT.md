# Live deployment

Keep the existing main-to-Cloudflare integration unchanged. Reconcile bot-generated production data before any owner-approved develop-to-main merge; see MAINTAINER_GUIDE.md. No new backend, map provider, domain or deployment infrastructure is required.

Canonical public beta: https://foodsafety.nemoneek.com/

Hosting: **Cloudflare Workers static assets**. The existing Git integration builds `main` and deploys only `site/`, never the repository root. Fallback: https://food-safety.shubha07m.workers.dev/

The project does not store Cloudflare credentials, account IDs, domain verification values or GitHub tokens. The existing authorized Cloudflare integration owns deployment. Repository visibility is a separate maintainer action; no script changes it.

## Build and deploy

`site/` is versioned, prevalidated static output with a blank browser configuration.
The deployment build runs `node scripts/build_deployment.mjs && npx wrangler deploy --config dist/wrangler.json`.
It supplies `GOOGLE_MAPS_BROWSER_KEY` through its own build environment; set
`REQUIRE_BROWSER_MAP_CONFIG=true` to require it. The Node-only build copies `site/`
into ignored `dist/site/`, adds runtime configuration there, and derives
`dist/wrangler.json` from the existing project settings. No Python build is needed.
The build command and environment must be configured before merging this change;
the Actions artifact check does not transfer its environment to the hosting build.
The existing custom-domain association remains unchanged. See [BROWSER_MAP.md](BROWSER_MAP.md).

GitHub CI checks code, data, tests and public output. The scheduled refresh runs every two hours and commits only validated public artifacts. Cloudflare Git integration observes changes to `main`. Its deployment status should be checked in the Cloudflare dashboard after any push; a successful GitHub push alone is not proof of deployment.

## Verification and rollback

Run `python scripts/verify_public_output.py` before committing artifacts. On the live URL, verify HTTPS, CSP, `frame-ancestors 'none'`, HSTS, `X-Content-Type-Options`, referrer and permissions policies with `python scripts/check_deployment.py`. That bounded check does not log cookies or credentials.

Cloudflare Workers static assets apply `site/_headers`. Domain-level security settings must not loosen them. Check English and `?lang=bn`, a record URL, data exports, correction links and the keyless map fallback. A deliberate live-map smoke contacts Google Maps; ordinary page load, fonts and translation remain local.

Rollback using Cloudflare deployment history to a previously validated version, then revert the corresponding generated-data commit if necessary. Do not force-push history as a routine rollback. Pause the refresh workflow during an accuracy incident and suspend disputed records using the documented CLI.

## Operational caveats

GitHub schedules are best-effort and may be delayed; public inactive repositories can have scheduled workflows disabled by GitHub. Watch occasional notifications. Only the last successful refresh timestamp signals success. A partial source failure can publish safe suspension changes while leaving the last-successful time unchanged.

Main protection on this private repository requires an eligible GitHub plan. Until available, retain single-maintainer writes, least-privilege workflows, local pre-push checks, green CI and no force-push/deletion. Once public, configure required CI and PR checks before accepting broader contributions.
