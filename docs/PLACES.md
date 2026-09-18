# Pandal restaurant discovery

This document describes the retained **Google provider**. The parallel regional
OSM snapshot, provider selection, attribution, and migration workflow are documented
in [Local nearby-food discovery](FOOD_POIS.md). The Google commands below remain
explicit operator operations; ordinary builds and visitor requests do not call them.

This is an operator-run data subsystem, separate from food-safety evidence ingestion.
Discovery is not an inspection, recommendation, quality judgment, or safety rating.
The website's Puja search consumes only the durable static contract. It never calls
Places on behalf of visitors or plots temporary restaurant coordinates.

## Flow and commands

Curated pandals → practical search zones → Places API (New) Nearby Search → bounded
supplemental circles when a primary result is saturated → deduplicate by place ID →
local Haversine reverse mapping → durable static JSON.

Activate the existing `food` environment first. From the repository root:

```bash
python -m food_safety.cli places validate
python -m food_safety.cli places plan
python -m food_safety.cli places discover --dry-run
python -m food_safety.cli places discover --zone bagbazar
python -m food_safety.cli places discover --max-calls 2
python -m food_safety.cli places remap
python -m food_safety.cli places usage
python -m food_safety.cli build
```

`validate`, `plan`, `usage`, and `discover --dry-run` make **zero HTTP requests** and
do not write files. Plans distinguish primary searches, potential/due supplemental
searches, the absolute geometric maximum, and the request/attempt ceilings. `remap`
makes zero HTTP requests; it purges expired
observations, rebuilds minimal historical association metadata, and returns current
runtime distances sorted within each pandal. Do not commit redirected runtime output.

`discover` skips fresh matching cached zones. Selective refresh uses `--zone`; an
expired observation or changed query configuration makes a zone due. No daily full
refresh is configured. The existing news `update` command does not call Google Places.
Partial failures return exit code 2 with sanitized reasons; successful zones can still
be saved. Failed zones retain their prior durable output and any still-valid cache.
Empty successful results replace that zone's temporary observations with an empty set.

Optional one-request diagnostic:

```bash
python -m food_safety.cli places discover --zone bagbazar --smoke-test
```

This forces a single selected zone, at most **one attempted request**, and at most ten
results. It persists quota accounting only—not fetched IDs, coordinates, names, or
associations. It cannot retry a failed call beyond that single attempt.

## Configuration and zone coverage

`config/places.yml` contains strict Pydantic-validated settings, pandals, optional manual
zones, and independently curated restaurant names. IDs must be unique. Enabled pandals
need sourced coordinates; disabled incomplete starter entries are allowed. Disabled
manual zones suppress their members rather than silently generating replacement zones.

Manual circles must cover every enabled member's entire target catchment. Unassigned
enabled pandals are grouped deterministically only when every pair materially overlaps
(default center distance ≤ 0.7 × the sum of catchment radii). Groups cannot exceed the
practical radius ceiling (default 1,500 m). This avoids single-link chains creating huge
circles. The API's absolute maximum is 50,000 m, not a recommended search radius.

Nearby Search uses `includedTypes: [restaurant]`, `rankPreference: DISTANCE`, and exactly
`places.id,places.displayName,places.location`. No Place Details, Maps JavaScript, or
consumer Google Maps scraping is used. Results are ranked and bounded (configured 20,
the API maximum), **not exhaustive**. A result-limit flag is reported when the cap is
filled. Reaching 20 is a saturation signal, not evidence of complete coverage. A
saturated primary may trigger up to three deterministic offset circles at bearings
0°, 120°, and 240°. Defaults use a 300 m center offset and 400 m supplemental radius;
the primary/catchment radius remains 600 m. The circles are bounded, revision-cached,
and never recurse. Unsaturated primaries trigger no supplemental request. All results
enter one global place-ID pool before local reverse mapping. Do not interpret even an
adaptive result set as comprehensive coverage.

The September 2026 audit split saturated multi-pandal circles into pandal-centered
manual zones. The adaptive layer improves candidate coverage within those deliberate
catchments without expanding a single circle indefinitely. Public discovery metadata
records primary saturation, supplemental count, raw/unique candidates, overlap, calls,
and association count, but never provider coordinates or raw responses.

Reverse mapping uses all usable observations, not just a zone's member list. A restaurant
can match several pandals. Distances are straight-line, not walking distances or travel
instructions. Newest unexpired coordinates win when zones return the same place ID.

## Retention and public contract

| Data | Location | Retention / meaning |
|---|---|---|
| Curated pandals/zones | `config/places.yml` | Durable, non-Google provenance |
| Independent restaurant names | `restaurants` in config | Durable; source URL required, Google sources rejected |
| Place IDs and Maps links | `data/places.json`, `site/data/places.json` | Durable Google identifiers; not Google business descriptions |
| Minimal associations | Same public JSON | `pandal_id`, `place_id`, `observed_at`, provenance only; historical discovery, **not current proximity** |
| Coordinates | Ignored `data/places-runtime/observations.json` | Seven days by default; hard maximum 30 days |
| Quota ledger | Ignored `data/places-runtime/usage.json` | Durable operational counters; preserve across runs/months |
| Raw responses, Google names, reviews, addresses, ratings, photos | Not stored | Response names are discarded in memory |

Every temporary observation has `fetched_at` and `expires_at`. Reads refuse expired or
future observations. Build, discovery, and remap delete expired entries atomically.
Remapping never extends expiry. A cache cannot declare a retention period over 30 days.
No Google coordinates or exact distances are written to static output or Git. Public
serialization uses a strict allowlist, also checked by `verify_public_output.py`.

An offline computer cannot execute cleanup: run `places remap` regularly while retaining
observations, and remove the **observations file only** at festival end. If operating
unattended, arrange a local cleanup invocation at least daily; it needs no API key and
makes no requests. Do not back up temporary observations indefinitely. Do not delete the
usage ledger as part of cache cleanup. Runtime data must not be uploaded as CI artifacts.

Public associations intentionally retain only an observed historical match. They must
not be used as a permanent coordinate surrogate or presented as a current distance/ranking.
Current distances require an unexpired local observation. A later interface must not claim
fresh proximity from the durable JSON alone. Independent restaurant metadata remains
separate under `curated`; there is no fallback to a stored Google display name.

Google Maps handoff URLs include **both** required `query` and `query_place_id`, for example:

```text
https://www.google.com/maps/search/?api=1&query=restaurant&query_place_id=PLACE_ID
```

`query=restaurant` is a generic fallback if Google cannot resolve an old ID; do not treat
the fallback search as confirmation of identity. Rich/current information is viewed at
Google Maps, not copied into this project's dataset.

## Keys, quota, and failure isolation

Enable Places API (New) and billing for the Google Cloud project if not already enabled.
Use `GOOGLE_MAPS_API_KEY` from the environment or the local ignored `.env` (a simple
`KEY=value` file; no shell expansion). Environment values take precedence. No key is
included in URLs, static data, error messages, or browser code. Restrict the server key
to Places API (New) and appropriate server application restrictions; browser referrer
restrictions are not suitable for this server-side command. Do not expose this key in JS.

Defaults: **3,000 attempts per UTC month**, warning at **2,500**, **60 attempts/run**, one
retry, 15-second request timeout, 128 KiB response ceiling, and at most three supplemental
searches per saturated primary (four searches total). The monthly and run ceilings can
be lowered. Each real HTTP attempt—including retries and failed requests—is reserved
on disk **before sending**. Twenty returned restaurants still count as one request.
Interrupted reservations may conservatively overcount; they never grant an unaccounted call.
An exclusive local process lock prevents concurrent runs consuming the same budget.

Only timeouts/network errors, 429, and selected 5xx errors are retryable. Authentication,
configuration, malformed responses, and redirects are not retried. Long `Retry-After`
values defer to a later operator run rather than sleeping or retrying early. Missing keys,
quota exhaustion, and provider failures do not affect food-safety evidence or its lifecycle.

The ledger fails closed if corrupt, or missing after initialization. Restore it from a
private operational backup; do not reset counters to get around a ceiling. Use a single
designated discovery workspace. This local guard does **not** aggregate another laptop's
or application's traffic. Moving to another runner requires migrating the private ledger
and reconciling the current month's usage first. Keep Google Cloud quotas/budget alerts
as an independent backstop. No GitHub secret is needed for the existing scheduled news
workflow, because it does not run Places discovery. No Cloudflare change is required.

The requested fields use Nearby Search Pro. Google's standard pricing page, checked
2026-09-15, lists 5,000 free monthly Pro requests; 3,000 is below that published allowance,
but other applications, billing-region terms, and pricing changes can affect actual cost.
The application does not claim a billing guarantee.

## Coordinate provenance

Map-ready pandals use reviewed OpenStreetMap objects referenced directly from the
curated pandal catalog. Precision is explicit: venue-level objects and approximate
street anchors are not interchangeable. These are independent geographic anchors,
**not verified current-year entrances, walking routes, or opening information**.
Unresolved catalog entries stay searchable without coordinates and do not appear as
markers. OpenStreetMap data is credited on the public map section; verify current
festival access before travel use.

## Website integration boundaries

The search-first Puja view consumes `site/data/places.json`, using only independently
curated names or neutral Google Maps handoff labels. Google Maps attribution and
terms/privacy links accompany this experience. Associations are historical, not current
proximity guarantees; no exact distances are displayed. The optional browser Google map
plots only curated pandals and reviewed food-safety anchors, not restaurant coordinates.
See [browser map setup and privacy boundaries](BROWSER_MAP.md). No visitor action calls
Nearby Search or Place Details. Food-safety evidence remains a separate module.

Zone planning, provider fetching, pure geometry, and serialization are separate modules.
Future optimization can propose validated zone config without changing the client or
quota guard. Density refinement should produce smaller bounded zone plans; selective
refresh should retain the same ledger and query fingerprint. Richer metadata requires a
separate provenance/retention decision. There is no Gemini clustering, database, queue,
server endpoint, per-visitor API call, or new background infrastructure in this feature.

Official references (reviewed 2026-09-15):

Restaurant quality filtering (ratings or review-count thresholds) is deferred.
It would change the requested field mask and potentially the SKU/cost. The
current list contains nearby restaurant links, not ranked recommendations.
The operator response uses Google's returned order; durable records are
deduplicated and serialized deterministically, so the public link list does
not claim to reproduce a Google ranking.

- [Nearby Search New](https://developers.google.com/maps/documentation/places/web-service/nearby-search)
- [Places policies and attribution](https://developers.google.com/maps/documentation/places/web-service/policies)
- [Service-specific terms §14: IDs and temporary coordinates](https://cloud.google.com/maps-platform/terms/maps-service-terms)
- [Maps URL parameters](https://developers.google.com/maps/documentation/urls/get-started)
- [Pricing](https://developers.google.com/maps/billing-and-pricing/pricing)

These implementation limits are conservative policy controls, not legal advice or a
claim that the project owns Google's content. Recheck the applicable agreement before
changing the public representation or retention behavior.
