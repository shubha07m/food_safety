# Aggregate site visits

The footer counter is first-party operational metadata, not an analytics product.
It never affects catalogs, featured ordering, food lists or evidence semantics.

## Definition

One visible, initialized page waits 1.5 seconds, then attempts one increment per
browser-tab session. A sessionStorage boolean (`foodpath-visit-v1=sent`) is written
before the request. Further page loads in that tab read the aggregate only. URL/region
changes within a page do not increment. No random identifier is generated.

It is **approximate site visits**, not unique people. New tabs/cleared storage can
count again; restored tabs can reuse a session. Failed attempts are not retried that
session. If sessionStorage is unavailable the client reads only. Robots or scripted
requests can affect totals; local storage is not an abuse boundary. There is no
backfill or estimate of past traffic: a new aggregate begins at zero.

## Mechanism and privacy

`site/visits.mjs` calls same-origin `/api/visits` without cookies. POST accepts only
empty JSON plus expected content type, same-origin Origin/Fetch-Site and a fixed
application header. GET reads the count. Other input/methods fail closed. No CORS
permission is granted. Direct clients can spoof headers, so this is basic cross-site
protection, not human verification.

`worker/visits.mjs` forwards only an internal method to one SQLite-backed Durable
Object. A transaction serializes aggregate increments. Only count, UTC day/minute
buckets and bucket totals are stored. No IP, user agent, location, identity, page
history, request body or individual visit record is persisted. Project observability
is disabled; hosting may still process transient request metadata under its policies.

Writes are bounded to 60/minute and 10,000/day globally. This may undercount bursts.
Limits protect writes, not Worker/DO request billing. Counter errors produce a quiet
unavailable response and the client hides the number; there is no retry loop and no
render-blocking request. The public site remains asset-first/static.

## Local validation and deployment

Plain `python -m http.server --directory site` has no endpoint: hidden counter is
expected. Unit tests use fixtures. Local runtime testing uses Wrangler without cloud
deployment or local operator variables:

~~~sh
CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV=false WRANGLER_SEND_METRICS=false \
  npx wrangler@4.136.3 dev --local --local-protocol https --port 8787 --persist-to .cache/counter-local
FOOD_SMOKE_ORIGIN=https://127.0.0.1:8787 FOOD_COUNTER_SMOKE=1 node scripts/browser_smoke.mjs
~~~

Use local HTTPS when testing the map iframe with production headers, which upgrade
insecure requests. The browser harness permits the emulator's local certificate;
production certificate and page policy requirements are unchanged.

The artifact builder copies the Worker outside `dist/site`, retaining blank tracked
browser configuration. `wrangler.jsonc` declares one binding and a `visits-v1`
SQLite-class migration. Ordinary static assets do not invoke the Worker first.
An approved deployment provisions the binding; no separate database platform,
account setting or paid subscription should be introduced for this feature.

## Plan gate and cost

Before release, the owner must check the actual account plan, available quotas and
the deployment's binding/migration preview. Free supports SQLite-backed Durable
Objects; exceeding Free allowances stops operations rather than creating paid overages.
Expected project traffic should fit, but the application cannot attest to account-wide
usage. Paid plans can incur overages; aggregate write caps do not cap request volume.
Do not auto-upgrade. Budget alerts are notifications, not spending ceilings.

Reviewed 2026-09-22: [Durable Objects pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/),
[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/),
[asset routing](https://developers.cloudflare.com/workers/static-assets/routing/worker-script/).
Recheck provider terms before deployment. No production counter existed before this
release; confirm `/api/visits` and the footer after an owner-approved merge/deploy.

If rollback is needed, hide/remove the client call and restore static asset routing
through a reviewed change. Preserve the aggregate namespace rather than deleting it
or resetting the count during routine deployments.
