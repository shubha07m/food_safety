# Privacy

Puja search, region selection, food lists and Food Safety filters read local static
data. Visitors make zero Google Places API calls and zero OSM API calls. Language,
region, selected Puja and California's Bengali-food view use URL parameters; they
do not require accounts or tracking storage.

**Open live Google map** is optional. Only that action loads the separate map
document and Google Maps JavaScript. Google then receives network information such
as IP address and origin under its [privacy policy](https://policies.google.com/privacy)
and [Maps terms](https://www.google.com/help/terms_maps/). No map loads on record-detail
or policy pages. Text/search fallback works
without Google. The map uses a separate browser-restricted configuration value, never
the operator Places or Gemini values. Origin-only referrers support map authorization.

Restaurant coordinate/verified-ID handoffs, sparse-catchment links and California's
regional Bengali-food searches navigate to Google Maps when followed. They are ordinary
external URLs, not background FoodPath API calls. Google's policies apply after
navigation. OSM-derived food data and approximate distance do not imply recommendations
or inspection results.

**Find Puja near me** requests browser location once per explicit click, never on
page load. The coordinates stay in page memory only; no location is sent to the
server, Google, the counter, URLs or storage. Local straight-line distance is compared
with published Puja anchors. Denying permission preserves regional browsing. No IP
geolocation or continuous location watch is used. World map shows public anchors,
not the user's position. Directions links contain the published venue destination,
not the user's origin.

The first-party **site visits** counter sends an empty JSON object after a visible
page has been open for 1.5 seconds. A sessionStorage boolean suppresses further
increments in the same tab session; later loads only read the total. No identifier,
cookie, IP, user-agent history, location or browsing history is stored by the counter.
It persists only aggregate count and minute/day rate-limit buckets. Browser restores,
storage restrictions, failed requests and bots affect accuracy; it is not unique
people. Clearing storage/new tabs may count again. Failure hides the counter without
retrying. [Counter details](docs/VISIT_COUNTER.md).

Share uses the native share sheet or copies a canonical region/Puja link. Venue/date
reports open a prefilled public GitHub issue; inspect it before submitting and do not
include private details. Nothing is automatically published.

There is no advertising, tracking pixel, profiling, application
cookie, account registration or visitor database. Hosting providers
may process IP addresses and operational logs. Other external source/GitHub links
are governed by their providers' policies; normal external links use no-referrer.

Food Safety community intake remains an optional outbound owner-configured Google
Form, not an embedded write endpoint. Puja suggestions use a public GitHub issue
form; a GitHub account is required and submitted text is publicly readable. Do not
include private contact details. The Puja review queue imports only the proposed
region and source URL, then retrieves the source separately. No public suggestion
automatically publishes; owner approval is required. Code discussions and
contributions on this public GitHub repository may also be publicly readable.

Food Safety Evidence remains West Bengal-only. It rejects social-identity inference
and unnecessary personal information. Business names and coarse reported areas need
source support; no private home addresses, owner family histories or employee/contact
lists are collected for that evidence dataset.

Scheduled Puja freshness monitoring sends no content to a model: it retains small
HTTP/check/hash receipts only. A successful fetch is not annual event verification.
Explicit operator extraction of changed unstructured sources remains separate.
Bounded public article passages may be sent to the configured model provider for
structured extraction. This sends no visitor data, form responses or private reviewer
notes. Review provider terms/data-use settings before operation. Model output must pass
source-grounded validation. Private research snapshots, candidates, operational ledgers
and model responses stay ignored and outside deployments; logs use counts/reason codes.
Routine evidence processing does not publish full article bodies. Minimal quotations
and provenance are retained, with necessity review on corrections/removal.

[Methodology](METHODOLOGY.md) · [Corrections](CORRECTIONS.md) ·
[Browser map](docs/BROWSER_MAP.md) · [Maintainer guide](docs/MAINTAINER_GUIDE.md).
