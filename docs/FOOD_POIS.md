# Nearby food: provider-neutral regional architecture

This is the technical reference for Puja FoodPath food discovery. It is separate
from West Bengal Food Safety Evidence and never implies an inspection or endorsement.

## Pipeline and regional boundaries

Regional OSM snapshot → normalized POIs → local spatial association → static JSON
→ named public food list → keyless Google Maps handoff.

`config/regions.yml` declares catalog geography, provider configuration and public
dataset paths. Kolkata uses `config/food.yml` in **hybrid** mode; California uses
`config/food-california.yml` in **osm** mode. Google-only and hybrid modes remain
available for comparison/rollback. Google data is never relabeled OSM.

Geofabrik Eastern Zone supplies the Kolkata research bbox; Geofabrik California
supplies the independently mapped California catchments. Raw PBF files and normalized
operator snapshots stay ignored. The retained California subset covers bounded
catchments, not a statewide food directory. Imports are explicit, never part of
ordinary builds or visitor requests.

## Model and normalization

Canonical IDs are `osm:node:ID`, `osm:way:ID`, or `osm:relation:ID`. Records preserve
provider/object identity, name if present, coordinates, category, optional cuisine,
snapshot and source provenance. Pyosmium reads nodes and polygonal features; area
representatives lie inside polygons, with explicit coordinate method. Duplicate
representations such as a tagged node within its matching named area are handled
conservatively; nearby chain branches are not fuzzy-merged.

Configured categories: restaurant, cafe, fast_food, ice_cream, food_court, bakery and
confectionery. Explicit private/access or abandoned/disused/demolished tags exclude
unsuitable records. Missing names/cuisine remain absent; absence of a lifecycle tag
does not prove a business is open.

## Local association

A grid index narrows candidates, then Haversine distance is compared with each
reviewed Puja's radius (currently 600 m). One POI can associate with multiple Pujas.
Unmapped Pujas never acquire fabricated proximity records. Associating another mapped
Puja from an existing regional snapshot needs no external discovery request.

Associations retain pandal ID, POI ID, provider, distance and snapshot identity.
Ordering is deterministic: distance, normalized name, stable ID. Straight-line distance
is approximate—not walking distance or a verified entrance location.

## Public presentation

Only meaningful **OSM-derived names** currently qualify as individual food rows.
Google-only anonymous associations remain in durable data for diagnostics, future
verified linking and rollback, but do not inflate the public list count.

The UI shows 12 rows initially and at most 20 after **Show more nearby food**.
The selected-list count describes that browsable dataset. Festival-food chips count
distinct named snapshot IDs within each catchment; overlapping catchments may repeat
a POI across Pujas. Featured eligibility needs reviewed geography plus named food,
preferring at least three names when enough curated entries qualify; at most six.

Mapped catchments without names show a sparse-data message and one keyless
restaurants-near-coordinate search link. Unmapped listings have no location-based
handoff. “No named snapshot listings” is not “no restaurants exist.”

## Handoff hierarchy

1. **Verified identity crosswalk:** Google Maps search URL with `api=1`,
   coordinate `query`, and `query_place_id`.
2. **No verified identity:** the same documented URL with `query=latitude,longitude`
   only. This opens the independently sourced OSM location, rather than a broad chain
   search. It does not assert Google's business identity or guarantee listing details.

Names stay visible in FoodPath; they are not needed in the coordinate URL. Parameters
are URL-encoded. Generating/following these links requires no FoodPath API key or
visitor Places request. [Official URL semantics](https://developers.google.com/maps/documentation/urls/get-started).

## Optional ID-only operator suggestions

Google Text Search (New), `POST /v1/places:searchText`, uses only
`places.id,nextPageToken`. Requests include a normalized name, regional context,
a 150 m rectangle and pageSize 3; additional pages are not fetched. Google may apply
text/location ranking: a lone returned ID is **not** verified identity evidence.

Statuses are unresolved, suggested or ambiguous. A next-page token also means
ambiguity. ID-only responses provide no display name/location to compare; neither
Gemini nor fuzzy logic upgrades them. Public crosswalk entries require explicit
operator-reviewed identity provenance and verification time, with status verified.
Suggestions are cached privately by POI/config revision and never copied into exports.

On 2026-09-19 Google's pricing table lists Text Search Essentials (IDs Only) as
unlimited/no unit charge. It still needs an authorized billing-enabled project and
method/project quotas; account terms and future pricing can differ.
[Text Search](https://developers.google.com/maps/documentation/places/web-service/text-search) ·
[Pricing](https://developers.google.com/maps/billing-and-pricing/pricing) ·
[Quotas](https://developers.google.com/maps/documentation/places/web-service/usage-and-billing).

The allowlist is regional. Eligibility uses meaningful names in each Puja's first
20 rows, globally deduplicated before requests. The explicit California pass allows
at most 60 unique candidates/attempts and shares the existing monthly Google ledger.
Every retry counts before send. Unchanged cached suggestions consume zero calls.

~~~bash
python -m food_safety.cli osm --region california validate
python -m food_safety.cli osm --region california stats
python -m food_safety.cli osm --region california import
python -m food_safety.cli osm --region california associate
python -m food_safety.cli build
# Inspect budget first; execute is a deliberate operator override of disabled-by-default.
python -m food_safety.cli osm --region california resolve-google --dry-run
python -m food_safety.cli osm --region california resolve-google --execute
python -m food_safety.cli places usage
~~~

Omit `--region california` for Kolkata. Imports require the configured local PBF;
use `osm --region california import --download` explicitly when a new extract is needed.
No visitor or ordinary build downloads it. See CLI help before real operations.

## California regional food searches

The registry also carries typed `regional_food_search` entries for Bengali-food
searches in the Bay Area, Southern California, Sacramento and all California.
They render only in California's secondary Bengali-food view. They have no POI ID,
coordinate, restaurant count or association: they are Google Maps search shortcuts,
not verified restaurants. The browser validates/reconstructs their keyless URLs.

## Data lifecycle, attribution and measured limits

Published OSM data carries **ODbL-1.0**, snapshot provenance and
**© OpenStreetMap contributors**, linked to
[OSM copyright](https://www.openstreetmap.org/copyright). The public JSON supplies the
OSM-derived dataset used for association; downstream reuse must assess applicable
ODbL obligations. Database publication and Produced Works are different concepts;
this project does not claim blanket permission to relicense source data.

Google place IDs have a storage exception. Google-derived coordinates remain in
ignored expiring runtime storage, at most 30 days, and never enter public OSM records.
Raw responses/names are not a permanent public Google listing cache.
[Google provider details](PLACES.md).

The initial five-Puja comparison did not justify replacing Google globally:
Kolkata OSM had 652 POIs, 618 named, 103 associations and 63 distinct associated
places; conservative named-OSM/all-Google sample ratio was 4.81%. This was not a
ground-truth or completeness benchmark. California's 2026-09-18 retained subset has
263 POIs, 246 named and 72 distinct named associated places across four mapped Pujas.
Different regions need different provider balances.

Refresh snapshots deliberately, record upstream time/hash and rebuild locally.
Ordinary builds reuse versioned data. Preserve prior reviewed snapshots/configuration
for rollback; switching provider does not delete Google IDs or replace evidence data.
Visitors make **zero OSM API and zero Places API requests**. Optional Maps JavaScript
visualization remains a separate lazy-loaded feature.
