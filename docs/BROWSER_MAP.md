# FoodPath homepage and optional browser map

The umbrella homepage separates Food Safety Evidence from search-first Puja FoodPath.
Pandal search uses `site/data/pandals.json` and `site/data/places.json`, with eight options at
most, English/Bengali names and area matching. `FEATURED_IDS` in `site/puja.mjs` is an
explicit editorial list capped at six. Disabled pandals are not published by the Places
pipeline. The source-backed catalog includes search-only entries without coordinates;
these never become guessed map markers.

Selected-pandal links use independently curated names or the neutral label “Restaurant
on Google Maps.” Associations are historical discoveries, not a current proximity
guarantee. This durable contract has no valid distances: the interface deliberately does
not display any. No restaurant is linked to inspection evidence by proximity or implied
to be safe, endorsed or inspected. No Places/Details call occurs in the visitor path.

## Two separate credentials

- `GOOGLE_MAPS_API_KEY`: private server/operator Places discovery only, unchanged.
- `GOOGLE_MAPS_BROWSER_KEY`: intended to be publicly visible, Maps JavaScript API only,
  protected by Google Cloud website and API restrictions.

Never reuse the server key. The build fails if the browser key equals a configured
Places or Gemini key. No real credential belongs in Git, including browser keys.

## Owner setup

1. In Google Cloud Console, select your billing-enabled project and enable **Maps
   JavaScript API**. Its map loads have separate pricing/quota from Nearby Search.
2. Create a **new** API key. Under **Application restrictions**, select **Websites**.
   Allow `https://foodsafety.nemoneek.com/*`. For local development add
   `http://localhost:8000/*` and `http://127.0.0.1:8000/*` (prefer a separate development
   browser key if practical). Do not permit arbitrary sites or unrestricted wildcards.
3. Under **API restrictions**, restrict the key to **Maps JavaScript API only**. Do not
   enable Places or server discovery APIs for this browser credential. Configure Cloud
   quotas/budget alerts; the operator's local 3,000-call ledger does not count map loads.
4. Set `GOOGLE_MAPS_BROWSER_KEY` locally in your ignored `.env` or shell environment.
   `.env.example` has only a blank placeholder. Do not put the value in tracked config.
5. Activate `food` and run:

   ```bash
   python -m food_safety.cli build
   python scripts/verify_public_output.py
   python -m http.server 8000 --bind 127.0.0.1 --directory site
   ```

6. Open `http://127.0.0.1:8000/`, scroll to geography and select **Open live Google map**.
   Confirm authorization, both layer toggles, source-marker filtering, and attribution.
   Missing/invalid authorization leaves the textual area list usable.

## Cost controls (documentation checked 2026-09-16)

Dynamic Maps and Places Nearby Search are separate billing paths. Normal visits
load local data only: zero map loads and zero Places requests. A fresh page requires
an explicit **Open live Google map** action. No preference auto-loads it on return.
Double-clicks and repeated initialization reuse one loader and one map. Layers,
selection, pan and zoom reuse that instance without Nearby Search. A failed load
stops without automatic retries. Frontend state prevents accidental duplicates;
it is not an abuse/security boundary or a monthly spending limit.

The operator Places ledger retains its 3,000-attempt monthly hard cap. Maps
JavaScript has no equivalent application monthly ledger. No Google tiles or
rendered map imagery are cached or captured for offline reuse by the product.

Google documents editable map-load quotas. In **Google Maps Platform → Quotas**,
select **Maps JavaScript API**, select the project-level **map loads per minute**
quota, choose **Edit**, and request **10 per minute** (or 5 for a small pilot).
Confirm the console accepts the lower value for your project; we cannot verify
your account's editable quota or approval result. Do not substitute a Places
quota. If unavailable, use the Console's quota support/request flow.

A QPM limit mitigates bursts but sustained usage can accumulate throughout the
month. Billing alerts notify; they do not cap spending. Review usage, current
SKU pricing, website/API restrictions, and quota settings periodically.

- [Official map quotas and edit steps](https://developers.google.com/maps/documentation/javascript/usage-and-billing)
- [Google cost controls and budget alerts](https://developers.google.com/maps/billing-and-pricing/manage-costs)

Festival-data refresh is separate: the existing Actions workflow checks a
persisted due-time guard (default six hours, maximum ten research runs/day).
It rebuilds our catalog without loading maps or running Places discovery.

The build creates **ignored** `site/maps-config.json`. It is an intended public browser
configuration, not a secret endpoint. Only the exact schema/value matching the configured
browser key is exempted by public-output verification; all other credential scanning
remains in place. Build without the variable (and remove its `.env` entry) to regenerate
the blank configuration. Do not commit the generated file or copy it into other JSON.

## Release wiring (not changed in this task)

An ignored artifact does not reach hosting through a Git push alone. The existing
deployment must run the static build with `GOOGLE_MAPS_BROWSER_KEY` available before
uploading `site/` for a keyed map. If it only uploads tracked files, it will safely show
the no-key fallback until the owner supplies that build-time environment/input. No
Worker code, Cloudflare account setting, domain, deployment workflow, or production
secret was changed here. Do not add this key to a bot commit. Browser smoke can test one
explicit live load with the restricted local browser key; that mode captures no imagery.

## Runtime and security boundaries

The homepage fetches only local JSON initially. On a deliberate click it creates a
same-origin `google-map.html` iframe. That document alone requests the Maps JavaScript
API, using the quarterly release channel and origin-only key authorization. It does not
load the Places library, request geolocation, or access restaurant coordinates. It plots
reviewed food-safety area anchors and independently curated pandals in different layers.
Coarse anchors are not establishment addresses. Google data-layer points avoid requiring
a new Cloud Map ID or deprecated marker API. Text/source filtering remains accessible
outside the map. No map frame is loaded on record-detail or policy pages.

`site/_headers` keeps the normal self-only CSP globally. Only `/google-map.html` and its
clean-URL alias detach that header and X-Frame-Options; the map document enforces its own
Google-compatible meta CSP. This is a static-asset security rule, not deployment
infrastructure reconfiguration. Main pages retain strict CSP, no-referrer and frame denial.
There is no static reusable CSP nonce. Map source strings are DOM text, never HTML;
postMessage handlers validate origin, source window, and marker fields. The dedicated
map page is intentionally not a standalone entry and needs a same-origin parent to load.

Google requests occur only after opting in. Policy links are next to the geography panel;
Google's map attribution must remain visible. The small text attribution on restaurant
links identifies Google Maps handoff separately from project-curated metadata. Existing
OSM area-anchor attribution remains visible. UI translations never translate source quotes.

Official references checked 2026-09-15:

- [Load Maps JavaScript API](https://developers.google.com/maps/documentation/javascript/load-maps-js-api)
- [Key setup and restrictions](https://developers.google.com/maps/documentation/javascript/get-api-key)
- [Maps CSP](https://developers.google.com/maps/documentation/javascript/content-security-policy)
- [Google Maps policies](https://developers.google.com/maps/documentation/javascript/policies)
- [Static header detachment](https://developers.cloudflare.com/workers/static-assets/headers/)
