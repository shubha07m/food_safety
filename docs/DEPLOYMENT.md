# Live deployment

Canonical public beta: https://foodsafety.nemoneek.com/

Hosting: **Cloudflare Workers static assets**. The existing Git integration builds `main` and deploys only `site/`, never the repository root. Fallback: https://food-safety.shubha07m.workers.dev/

The project does not store Cloudflare credentials, account IDs, domain verification values or GitHub tokens. The existing authorized Cloudflare integration owns deployment. Repository visibility is a separate maintainer action; no script changes it.

## Build and deploy

`site/` is a versioned, prevalidated static artifact. Cloudflare needs no Python build to serve it. Set the Workers Builds deployment command to `npx wrangler deploy` (Cloudflare-managed environment); the local `wrangler.jsonc` specifies `site/`. Do not install global tooling or expose any tokens in the frontend. The existing custom-domain association remains in the Cloudflare dashboard.

GitHub CI checks code, data, tests and public output. The scheduled refresh runs every two hours and commits only validated public artifacts. Cloudflare Git integration observes changes to `main`. Its deployment status should be checked in the Cloudflare dashboard after any push; a successful GitHub push alone is not proof of deployment.

## Verification and rollback

Run `python scripts/verify_public_output.py` before committing artifacts. On the live URL, verify HTTPS, CSP, `frame-ancestors 'none'`, HSTS, `X-Content-Type-Options`, referrer and permissions policies with `python scripts/check_deployment.py`. That bounded check does not log cookies or credentials.

Cloudflare Workers static assets apply `site/_headers`. Domain-level security settings must not loosen them. Check English and `?lang=bn`, a record URL, data exports, correction links and the local map. No external map/font/translation request is needed.

Rollback using Cloudflare deployment history to a previously validated version, then revert the corresponding generated-data commit if necessary. Do not force-push history as a routine rollback. Pause the refresh workflow during an accuracy incident and suspend disputed records using the documented CLI.

## Operational caveats

GitHub schedules are best-effort and may be delayed; public inactive repositories can have scheduled workflows disabled by GitHub. Watch occasional notifications. Only the last successful refresh timestamp signals success. A partial source failure can publish safe suspension changes while leaving the last-successful time unchanged.

Main protection on this private repository requires an eligible GitHub plan. Until available, retain single-maintainer writes, least-privilege workflows, local pre-push checks, green CI and no force-push/deletion. Once public, configure required CI and PR checks before accepting broader contributions.
