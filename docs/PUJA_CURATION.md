# Puja pandal curation

The Puja catalog is source-backed project data, separate from food POI discovery.
`config/regions.yml` declares regions and their additional reviewed catalog files.
`config/puja.yml` plus the registry's regional `config/puja-*.yml` files are the publication boundary.
The static build writes
only validated records to `data/pandals.json` and `site/data/pandals.json`.

## Commands

```bash
python -m food_safety.cli puja sources validate
python -m food_safety.cli puja discover
python -m food_safety.cli puja extract --max-calls 3
python -m food_safety.cli puja review-summary
python -m food_safety.cli puja publish
python -m food_safety.cli puja stats
python -m food_safety.cli puja refresh
python -m food_safety.cli puja geocode --dry-run --pandal PANDAL_ID
python -m food_safety.cli puja geocode --pandal PANDAL_ID
python -m food_safety.cli puja geocode-summary
```

`discover` fetches only enabled, explicitly configured public URLs. Existing URL, DNS,
robots, timeout and response-size controls apply. Frozen passages stay under ignored
`.cache/puja/sources/` and are never public artifacts.

`discover` recognizes supported JSON-LD Event records deterministically; `extract`
uses those grounded candidates first, with no model call. Structured source tables can
also be reviewed directly. Unstructured sources use the explicit bounded Gemini adapter.
Source text is untrusted data. The model may
propose names, Bengali names, aliases, areas, organizers, years, venue/address/date text only with
passage IDs and verbatim quotes. Application code proves each quote and value occurs in
the frozen passage using exact, NFC or whitespace-normalized matching. A model cannot
publish, geocode, rank or create a Google Maps request. Calls are capped per run and cached
by source revision, model, task and schema.

`review-summary` reports private candidates without printing source bodies. A maintainer
must inspect citations and add supported values to `published` in `config/puja.yml`.
`publish` validates provenance, coordinates and IDs before generating public data.

`geocode` is an explicit operator research aid for a small named set of already
source-backed pandals. It uses the public Nominatim service single-threaded at no more
than one request/second, sends a project User-Agent, caches under ignored `.cache/`,
and accepts at most 30 calls/run. It never edits the catalog or publishes a result.
Review identity, precision and the linked OpenStreetMap object before adding a coordinate
to `config/puja.yml`. Ambiguous and distant name matches must be rejected. Respect the
[Nominatim usage policy](https://operations.osmfoundation.org/policies/nominatim/);
this tool is not a bulk geocoder.

## Publication requirements

### Profiles and two public tiers

The selected Puja is a profile article; nearby food begins below it. The public
label is derived from reviewed edition data, not a separate confidence score:

- **Source-listed · current venue not reviewed**: identity and region are sourced;
  no current-edition confirmation is asserted.
- **YEAR event confirmed**: that edition is explicitly reviewed. **YEAR venue/date
  reviewed** additionally requires its reviewed location and supported date.

`official_links` retain kind, URL and supporting source evidence. Optional `about`
contains a short neutral sourced introduction. `edition.programme_notes` holds
at most three sourced highlights; artist names remain ordinary note text. Notes
from a previous edition are not displayed as current. Social links need reviewed
organizer ownership/relationship, not just a plausible account name.

`edition.location` is an atomic venue/address/independent-anchor override. An
optional edition city prevents an old municipality leaking into a moved venue's
profile or restaurant handoff; unsupported city context is omitted. An
edition without this override cannot inherit stable-record coordinates. Prior-year
edition locations remain historical, not current map, Near Me, directions or food
anchors. Undated legacy anchors remain visibly last-known. Map anchors can be
approximate; Near Me requires venue precision. Directions additionally require a
current, confirmed, venue-reviewed edition. One effective-location contract drives
both browser behavior and local food association. Food coverage records an anchor
key, preventing old-catchment results from appearing after a venue move.

### Manual private lead campaign

`puja leads` is an operator CLI action, **not a scheduled workflow**:

```bash
python -m food_safety.cli puja leads --seeds .cache/puja/seeds.json \
  --campaign autumn-review --max-calls 5 --dry-run
python -m food_safety.cli puja leads --seeds .cache/puja/seeds.json \
  --campaign autumn-review --max-calls 5
```

Supply a JSON array of at most 40 seeds: `region`, `url`, optional `source_kind`
and `candidate_name`. Lead mode extracts only identity/locality/source links.
An explicitly supplied name can be screened against frozen passages without a
model. `mode: profile` requires `accepted_identity` and requests richer facts only
for an accepted research subject; this is not publication approval.

JSON-LD Event extraction precedes Gemini. Messy prose uses the existing structured
adapter, not a bespoke page parser. Optional `content_selector` narrows a reviewed
page section. `suggest_links` returns bounded one-hop suggestions for operator
review; it never follows them. An explicit `allow_missing_robots` permits only a
literal robots 404, not blocked requests. Redirects remain on approved seed hosts.

Private frozen sources, model responses, attempt ledger and review packet live in
ignored `.cache/puja/campaigns/CAMPAIGN/`. Reuse the same campaign ID to retain its
hard **20 attempted model calls**, including failures; each invocation allows at
most five and defaults to zero. HTTP attempts, including robots/redirects, stop at
120 per campaign. There are no automatic retries. A provider failure stops further
model work in that batch. Revision/model/task/schema-aware responses are reused.
Review packets from successive lead/profile batches are retained together.

Packets include literal support, missing fields, duplicate/source warnings,
date/year/timezone inconsistencies, tentative tier and unreviewed geography.
Literal matching does **not** prove a fact belongs to the same event or year.
An owner must approve organizer identity, edition relationships, links, conflicting
announcements and final publication. Fetch/model failure defers a candidate; no
code path here writes public catalogs. Publication remains an explicit reviewed
configuration edit. This campaign is separate from automatic HTTP monitoring.

Every published pandal has a stable ID, name, area, city/region, source URL, title,
supporting quote and verification timestamp. Coordinates are optional. If present they
require an independent non-Google source and explicit precision; they are never inferred
from a name or generated by Gemini. District is optional and must not be inferred
from a publisher's broad regional category.

Local search covers sourced English/Bengali names, aliases, area, neighbourhood and city
within the selected region. Stable existing IDs survive regional normalization. Region,
country, administrative area, city and coordinate bounds must agree with the registry;
Howrah is not silently treated as Kolkata municipality. Private candidates and raw
model responses never enter Git.

## Five-region catalog and annual editions

California currently has six organizer-source-backed 2026 listings and four reviewed
OSM venue anchors. Sources include Pashchimi, Sanskriti, BASC, Valley Bengali Community,
Agomoni and Ankur; exact URLs, short support and timestamps live in the reviewed
California configuration. Missing or tentative venues stay unmapped. An organizer's
identity does not verify a venue by itself; corroborate the published address and
independent geographic object separately.

London region, Toronto / GTA and Melbourne each begin with two organizer-backed
listings and independently reviewed geographic anchors. London includes Camden and
BCSC; GTA includes Durba and APCAT; Melbourne includes MELBA and BSM. Exact organizer
URLs/quotes are in each regional config. Camden remains a source-backed listing without
an inferred 2026 edition. The other five new records carry explicitly sourced dates.
APCAT is an address/street anchor; BSM is an approximate racecourse-area anchor, not a
reviewed entrance. Their precision must remain visible and does not qualify for exact
venue directions. Catalog regions need not follow municipal boundaries.

`edition` separates annual facts from stable listing identity: supported year,
confirmation, start/end dates, IANA timezone, venue review, review time and evidence.
Never infer year from copyright, reachability or weekday coincidence. Existing legacy
`year`/`event_dates` do not automatically become reviewed edition data.

Source and extractor configuration is region-aware. California and the new listings
were manually source-reviewed, not generated from model memory. Do not run a West
Bengal-geocoding context against another region.
Add a future region through registry metadata, explicit source-backed catalog records,
independent anchors and a regional food configuration; validate bounds and provenance
before publication. Never infer an organization's translated name or venue.

Search, featured eligibility, map bounds and nearby food are region-scoped. Featured
Pujas require reviewed geography and meaningful named food; prefer three names when
enough eligible curated records exist, with a maximum of six. Food Safety Evidence
remains West Bengal-only regardless of Puja region expansion.

## Safe expansion workflow

1. Add a bounded reputable source URL to `sources`.
2. Run discovery and extraction.
3. Inspect the private candidate summary and its retained quotes.
4. Confirm names, locality, year and any coordinates in the source itself.
5. Add only supported values to `published`; leave unsupported values null.
6. Validate, publish, build and run the public-output gate.

Prefer municipal/tourism pages, organizer pages, and established Bengali or English
publications. Do not scrape Google Maps, copy unsourced AI lists, or treat social posts and
SEO compilations as authoritative without an independently reviewable source.

## Current seed and limits

The 2026-09-16 catalog includes reviewed factual rows from Indian Festival Diary's
2025 North Kolkata, South Kolkata and Howrah tables. These are directory listings,
not confirmation of 2026 venues, hours, admission, or municipal boundaries. The
source's broad zones include surrounding districts. `location_precision=source_zone`
preserves that limitation; `district` and coordinates remain null unless a separate,
reviewed coordinate source is attached. Exact short
row evidence and the frozen source revision accompany every imported record.
Ambiguous generic names and possible duplicates were excluded. Bengali names, aliases,
organizers and coordinates were not inferred. A limited subset now has independently
reviewed OpenStreetMap venue/street anchors; unresolved entries remain searchable but
unmapped. This is a source-backed catalog, not a complete list.

Structured tables can be curated directly without model inference. Gemini remains
useful for prose. The bounded live run encountered provider quota errors, so no
model-generated facts were added from it.

## Scheduled monitoring, not scheduled extraction

`puja refresh` runs inside **Refresh Food Safety Data** without changing its evidence
schedule. It checks at most five due known sources, least-recently-attempted first.
Each source is due daily during September–October and weekly otherwise. The existing
two-hour workflow wakeup drains due batches; it is not a two-hour-per-source refresh.
Manual invocation uses the same due/batch controls. There is no bulk crawler.

The monitor uses ETag first, then Last-Modified, otherwise normalized relevant-text
hashing. DNS-pinned transport, robots checks, redirects, size/time bounds and host
spacing remain enforced. An unchanged source only updates its check receipt. Changed
or initially unreviewed revisions are pending; no record is published, removed or
silently moved and **no scheduled Puja Gemini call occurs**, even for changed content.

`data/puja_refresh.json` stores small attempt/success timestamps, URL, bounded HTTP
validators, content hash, reviewed revision, pending flag and separate extraction
status. No raw pages or model payloads are committed. A failed fetch keeps the last
successful timestamp. First checks establish an unreviewed baseline, not confirmation.

After reviewing the current source, maintainers can set `reviewed_revision` on its
SourceSpec to the exact receipt hash. Review annual evidence separately in `edition`.
Use `puja discover --source ID` then `puja extract --source ID --max-calls 1` only when
explicitly needed; deterministic JSON-LD precedes the bounded cached model path.
Private candidates remain review-only and need not be extracted just because a page
changed. Catalog rebuild and monitoring make no Google calls.

`allow_missing_robots: true` is a reviewed exception for literal 404 responses
at `/robots.txt` only, consistent with [RFC 9309](https://www.rfc-editor.org/rfc/rfc9309.html#section-2.3.1.3).
403, explicit robots restrictions, network failures and article 404s remain
blocking. `content_selector` narrows extraction to the reviewed source table/title.
