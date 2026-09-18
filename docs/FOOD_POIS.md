# Local nearby-food discovery

OSM supplies a regional candidate snapshot. Local geometry associates places with
independently located pandals. Static JSON serves visitors. Google Maps is a
handoff destination; optional Google discovery remains available for comparison
and sparse neighborhoods. Neither provider is a complete or current venue census.

## Operator workflow

Use the existing `food` environment. Only import needs the optional binary reader:

```bash
python -m pip install --only-binary=:all: 'osmium==4.3.1'
python -m food_safety.cli osm validate
python -m food_safety.cli osm import --download
python -m food_safety.cli osm stats
python -m food_safety.cli osm bakeoff
python -m food_safety.cli osm associate
python -m food_safety.cli build
```

The pinned pyosmium wheel is an optional Python extra (`.[osm]`), not a system
package. The same commands work on supported macOS and Linux wheels. No silent
installation occurs. A missing reader produces an installation message.
`osm import --source /path/to/extract.osm.pbf` accepts an already downloaded PBF
(OSM XML also works for small fixtures). Ordinary builds never download or parse
PBFs and do not require pyosmium.

The first download is explicit, HTTPS-only, size-limited to 400 MB, and restricted
to Geofabrik, including redirects. Later imports reuse the local file. Use
`osm import --download --refresh` deliberately to obtain a new extract. There is
no scheduled OSM download and no public Overpass dependency. Import identity is
the file SHA-256 plus configuration; unchanged imports reuse their normalized
snapshot. Increment the normalization version when transformation rules change.

## Region and normalization

The maintained [Geofabrik India Eastern Zone extract](https://download.geofabrik.de/asia/india/eastern-zone.html)
was the smallest listed regional parent covering both cities when checked on
2026-09-17. No West Bengal sub-extract was listed in the
[India inventory](https://download.geofabrik.de/asia/india.html). Verify upstream
availability before changing the configured URL; do not download the planet.

`config/food.yml` specifies the local research box. Its bounds are the envelope
of the 14 independently located pandals plus a 10 km geodesic margin, rounded
outward. This is **not** an administrative boundary or a claim of citywide
coverage. A complete pandal catchment must fit inside the imported region.
New located pandals inside that region can be associated without any API call.
Unlocated catalog entries remain unavailable for spatial discovery.

Categories are configurable: restaurant, cafe, fast_food, ice_cream, food_court,
bakery, confectionery. Explicit private/no access and disused, abandoned,
demolished, razed, removed, construction or proposed lifecycle tags are excluded.
Absence of a lifecycle tag does not prove a business is still operating.

Libosmium reads nodes and assembles closed ways/multipolygon relations. Areas use
a scanline interior representative point respecting holes, not an invented street
address. Open ways use their middle vertex. Unsupported relation geometries and
invalid geometries are counted. Original OSM type/ID, object URL, tags, timestamp
and point method remain attached to each record. NFC/whitespace normalization
does not invent names, translations or cuisine.

Deduplication removes repeated object IDs and equal-name/category node-in-area
or explicit relation-member representations. Nearby same-name chain branches
are **not** fuzzy-merged. This is conservative: some duplicate physical venues
can remain where OSM representations provide insufficient identity evidence.

## Local association and provider modes

The shared grid-prefilter/Haversine join accepts either provider's points. Each
food place can belong to multiple pandals within their configured catchment
(currently 600 m). OSM ordering is distance, normalized name, stable object ID.
Distances mean approximate straight-line distance, not walking distance.

`config/food.yml: provider` accepts:

- `google`: original durable Google dataset and generic labels; rollback path.
- `osm`: only OSM-derived snapshot matches.
- `hybrid`: OSM snapshot matches first, original Google links afterward.

Google links are suppressed as duplicates only for explicitly verified identity
links. Unresolved providers can represent the same venue; proximity alone never
establishes equivalence. OSM-first ordering is provider presentation, not a quality
ranking. Within each OSM list, distance ordering is deterministic. The first 15
items render initially; “Show more nearby food” adds another 15.

Run `osm bakeoff` before changing the default. It compares five existing 600 m
catchments using only unexpired Google coordinate observations, without new Google
calls. Google display names were intentionally not retained, so the report leaves
Google named/unnamed counts unknown. The ratio uses all active Google IDs as a
conservative upper-bound reference, **not** a measured named-coverage denominator.
It cannot identify Google-only versus OSM-only venues. A 70% reference threshold
is an engineering aid, not proof of complete coverage; inspect individual areas.

## Data contracts and ODbL

### First measured migration decision (2026-09-17)

The 2026-09-16T20:21:21Z snapshot yielded 652 POIs, 618 named (94.79%),
after two equal-name node/area representations were merged. All 14 mapped
pandal catchments were evaluated; 12 contain OSM matches (103 associations,
63 distinct places). The other 209 catalog entries still lack coordinates.

| Catchment (600 m) | Active Google IDs | OSM places | Named OSM |
| --- | ---: | ---: | ---: |
| Bagbazar | 53 | 0 | 0 |
| Ekdalia | 100 | 13 | 13 |
| Chetla | 52 | 1 | 1 |
| Salkia | 55 | 1 | 1 |
| Naktala | 52 | 0 | 0 |

The reference ratio is 15/312 (4.81%), nowhere near the proposed threshold.
**Hybrid is the development default; OSM-only is not justified.** Named OSM
matches improve some lists but do not replace Google's coverage. No identity
overlap or exhaustive-coverage claim is made; zero OSM records means a snapshot
gap, not absence of food places. The 762 durable Google IDs remain untouched.

Native-filtered regional PBF import took 8.98 s on the development laptop.
The grid join took 0.030 s for 1,000 test pandals against the real 652-point
snapshot, and 0.072 s against a synthetic 10,000-point regional pool on the
development laptop. These are illustrative measurements, not performance SLAs.

`data/osm-runtime/` is ignored: raw PBF, normalized operator snapshot, comparison
reports and optional Google ID suggestions. `data/osm_food.json` and its site copy
publish the entire normalized regional subset and associations, including OSM
provenance, upstream snapshot date when available, SHA-256, extraction timestamp,
box, diagnostics and **ODbL-1.0** metadata. This data has its own license; it is not
relicensed under the application's code license.

The restaurant UI shows **© OpenStreetMap contributors**, links to
[OSM copyright](https://www.openstreetmap.org/copyright), and offers the downloadable
OSM-derived dataset. Database publication is not merely a Produced Work. Follow
the [ODbL](https://opendatacommons.org/licenses/odbl/1-0/),
[OSMF attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines)
and [Produced Work guidance](https://osmfoundation.org/wiki/Licence/Community_Guidelines/Produced_Work_-_Guideline),
including applicable attribution/share-alike and access requirements. This is an
engineering implementation of those boundaries, not a legal opinion about every
possible future combined database.

Google data stays in the existing `places.json` contract. Its temporary coordinate
observations never enter the OSM dataset. `food_provider.json` carries provider
choice and any independently verified cross-provider identity links separately.
Do not publish Google-derived names, coordinates or other content as OSM tags.
Do not copy data from Google consumer pages into OSM.

## Maps handoff and optional ID suggestions

An OSM name/category plus independent coordinates forms a URL-encoded
`https://www.google.com/maps/search/?api=1&query=...` link. Creating that link
requires no Google API request. `query_place_id` is added only for an explicitly
verified cross-provider link. See [Maps URLs](https://developers.google.com/maps/documentation/urls/get-started).

Optional `osm resolve-google --dry-run` plans globally deduplicated, named POIs
from a configured pandal allowlist. `google_enrichment.enabled` defaults to false.
An explicit enabled run uses Text Search (New), field mask
`places.id,nextPageToken`, page size 3, a small location restriction, and no other
fields. Responses are ID-only suggestions in ignored storage. Even one result
is **not identity proof**; multiple results/page continuation are ambiguous.
No suggestion is automatically attached. Verified links require an independent
identity source, timestamp and explanatory note in operator configuration.

On 2026-09-17 the official [Text Search documentation](https://developers.google.com/maps/documentation/places/web-service/text-search)
and [pricing table](https://developers.google.com/maps/billing-and-pricing/pricing)
listed Text Search Essentials (IDs Only) with unlimited free usage. Review current
terms before enabling; this is not a permanent price promise. API/project quotas
still apply. [Place IDs](https://developers.google.com/maps/documentation/places/web-service/policies)
have a storage exception; that does not extend to other Google content.
Every actual attempt, including retries, consumes the shared conservative local
3,000/month Google operation guard, with its own bounded per-run plan (default
10 attempts). Existing Nearby Search accounting and limits are retained.

## Serving and rollback

Visitors fetch static project JSON only: zero OSM API and zero Places API requests.
The optional click-to-load Google map is a separate rendering path and unchanged.
No food listing implies recommendation, inspection, endorsement or safety.

Builds use the committed OSM subset, never a silently newer local runtime snapshot.
Re-association is deterministic from that snapshot plus current sourced pandal
coordinates. To roll back the list, set `provider: google` and build; existing
Google IDs/associations have not been deleted. Google saturation-aware Nearby Search
remains an explicit operator comparison/selective-discovery option, not a build
side effect. No ordinary page request or build triggers enrichment.
