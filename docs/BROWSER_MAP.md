# Optional browser map and configuration delivery

Puja FoodPath uses region-scoped local search and reviewed map anchors across five
regions. Selected-region and world scopes reuse one optional Google map. World mode
contains Puja anchors only, with restrained coral-ring/cream-centre markers.
Food Safety Evidence remains West Bengal-only; its optional area layer is absent
outside Kolkata and in world mode.
Restaurant coordinates are not sent to this map. Food lists are static; see
[FOOD_POIS.md](FOOD_POIS.md).

## Tracked source versus runtime output

Tracked `site/maps-config.json` must remain `{"browser_key":""}`. Normal Python
builds always write that blank default, regardless of local environment. A plain
`python -m http.server --directory site` therefore shows the intentional fallback.
A local `.env` does not make this static server a configured live-map deployment.

`node scripts/build_deployment.mjs` copies validated `site/` to ignored
`dist/site/`, then injects `GOOGLE_MAPS_BROWSER_KEY` into **that copy only**.
It reads the process environment, not `.env`, and requires a fresh output directory.
It also derives `dist/wrangler.json` from existing deployment settings.
Never manually populate the tracked file.

- `GOOGLE_MAPS_BROWSER_KEY`: browser-restricted Maps JavaScript configuration.
- `GOOGLE_MAPS_API_KEY`: private operator Places calls, never browser output.
- `GEMINI_API_KEY`: private structured extraction, never browser output.

The artifact builder rejects reuse of a configured private key as the browser value.
Current-tree/index guards reject populated tracked map configuration. Runtime validation
permits only the designated browser value in the isolated artifact.

## Deliberate local live-map test

Supply the restricted browser value through your local environment without printing
or saving it in tracked files. With a fresh ignored `dist/` output:

~~~sh
node scripts/build_deployment.mjs
python scripts/verify_public_output.py --runtime --site dist/site
python -m http.server 8000 --bind 127.0.0.1 --directory dist/site
~~~

Use the same environment for artifact generation and verification. Set
`REQUIRE_BROWSER_MAP_CONFIG=true` to make absent configuration fail the build.
Inspect any existing output before moving/removing it; do not reuse stale artifacts.
The keyless workflow remains `python -m food_safety.cli build` and serving `site/`.

## Production boundary

Actions builds/tests tracked output and commits only an explicit generated-file
allowlist; map configuration is excluded. Its separate artifact check is not a deploy
and does not transfer environment values to the hosting build.

The existing hosting build independently receives `GOOGLE_MAPS_BROWSER_KEY` and runs:

~~~sh
node scripts/build_deployment.mjs && npx wrangler deploy --config dist/wrangler.json
~~~

Static assets come only from `dist/site/`. The isolated artifact also includes the
aggregate-counter Worker and its binding configuration; it never receives operator keys.
[Deployment](DEPLOYMENT.md) documents verification and rollback.
`python scripts/stage_generated.py` validates checkout/index; `--stage` uses the
explicit allowlist. `python scripts/verify_public_output.py` checks tracked output.

## Loading and cost behavior

A fresh visit makes **zero map loads**, **zero Places calls**, and **zero OSM API
calls**. Only **Open live Google map** creates the same-origin map iframe and loads
Maps JavaScript. No stored preference silently reloads it on a future visit.
Double-clicks, region switches, selected-Puja changes and layer toggles reuse a
singleton loader/map. A failed load stops without an automatic retry loop.

Dynamic Maps rendering is a separate billing path from operator Nearby/Text Search.
The Google operation ledger has a 3,000-attempt monthly internal cap; Maps JavaScript
has no equivalent application-side monthly ledger. Frontend deduplication is not an
abuse boundary. No Google map tiles or rendered imagery are cached for offline reuse.

Recommended Google Cloud configuration (owner-controlled):

1. Restrict the browser key to **Maps JavaScript API only**.
2. Restrict website referrers to `https://foodsafety.nemoneek.com/*`; allow
   `http://localhost:8000/*` and `http://127.0.0.1:8000/*` only if needed.
3. In Google Maps Platform quotas, inspect Maps JavaScript's map-loads-per-minute
   quota. Request a conservative 5–10/minute if that editable quota is available;
   confirm the console accepts it for the project.
4. Review usage, API/referrer restrictions, billing alerts and current pricing.

A per-minute limit mitigates bursts, not sustained monthly cost. Alerts notify rather
than impose a spending ceiling. Pricing/quota options can change.
[Official quotas](https://developers.google.com/maps/documentation/javascript/usage-and-billing) ·
[Cost controls](https://developers.google.com/maps/billing-and-pricing/manage-costs).

## Runtime boundaries and accessibility

The main page reads local JSON and keeps strict script policy. Only the opt-in
`google-map.html` document permits required Google endpoints; it validates message
origin and sending window. Public anchors are rendered as text, never source HTML.
The map document loads no Places library, requests no visitor geolocation and is not initialized
on record-detail or policy pages.

The parent Puja page has a separate explicit **Find Puja near me** control.
`Permissions-Policy` allows geolocation only for the same origin; the map document
explicitly disables it. One browser request per click feeds local Haversine distance
against published anchors, showing up to five within 100 km. No coordinate is persisted,
sent to Maps/counter, or put in the URL. Permission denial and unavailable locations
fall back to region browsing. HTTPS (or loopback development) is required.
Near Me, world markers, search and food chips share the global-ID selection resolver.

Textual geography, regional search and food lists remain usable without the live map.
Puja markers appear first; source labels and precision remain visible. Area anchors
do not locate inspections or establishments. Attribution stays visible, and UI
translation never replaces original evidence.

[Maps loader](https://developers.google.com/maps/documentation/javascript/load-maps-js-api) ·
[Key restrictions](https://developers.google.com/maps/documentation/javascript/get-api-key) ·
[Maps CSP](https://developers.google.com/maps/documentation/javascript/content-security-policy) ·
[Privacy](../PRIVACY.md).
