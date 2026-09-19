# Privacy

Puja search, region selection, food lists and Food Safety filters read local static
data. Visitors make zero Google Places API calls and zero OSM API calls. Language,
region, selected Puja and California's Bengali-food view use URL parameters; they
do not require accounts or tracking storage.

**Open live Google map** is optional. Only that action loads the separate map
document and Google Maps JavaScript. Google then receives network information such
as IP address and origin under its [privacy policy](https://policies.google.com/privacy)
and [Maps terms](https://www.google.com/help/terms_maps/). No map loads on record-detail
or policy pages, and no visitor geolocation is requested. Text/search fallback works
without Google. The map uses a separate browser-restricted configuration value, never
the operator Places or Gemini values. Origin-only referrers support map authorization.

Restaurant coordinate/verified-ID handoffs, sparse-catchment links and California's
regional Bengali-food searches navigate to Google Maps when followed. They are ordinary
external URLs, not background FoodPath API calls. Google's policies apply after
navigation. OSM-derived food data and approximate distance do not imply recommendations
or inspection results.

There is no project analytics, advertising, tracking pixel, profiling, application
cookie, account registration, public write API or visitor database. Hosting providers
may process IP addresses and operational logs. Other external source/GitHub links
are governed by their providers' policies; normal external links use no-referrer.

Community intake is an optional outbound owner-configured Google Form, not an embedded
write endpoint. Responses must remain private, with no uploads, email collection or
public response summaries requested by this project. No submission automatically
publishes. Do not submit unnecessary personal information. Code discussions and
contributions on this public GitHub repository may be publicly readable.

Food Safety Evidence remains West Bengal-only. It rejects social-identity inference
and unnecessary personal information. Business names and coarse reported areas need
source support; no private home addresses, owner family histories or employee/contact
lists are collected for that evidence dataset.

Bounded public article passages may be sent to the configured model provider for
structured extraction. This sends no visitor data, form responses or private reviewer
notes. Review provider terms/data-use settings before operation. Model output must pass
source-grounded validation. Private research snapshots, candidates, operational ledgers
and model responses stay ignored and outside deployments; logs use counts/reason codes.
Routine evidence processing does not publish full article bodies. Minimal quotations
and provenance are retained, with necessity review on corrections/removal.

[Methodology](METHODOLOGY.md) · [Corrections](CORRECTIONS.md) ·
[Browser map](docs/BROWSER_MAP.md) · [Maintainer guide](docs/MAINTAINER_GUIDE.md).
