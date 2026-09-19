import test from 'node:test';
import assert from 'node:assert/strict';
import { combineFood, osmMapsURL, publicFood, foodGeography, pandalFoodURL, INITIAL_FOOD_LIMIT, MAX_FOOD_LIMIT } from '../site/nearby-food.mjs';

const poi = (id = 1, name = 'মিত্র Cafe & Food') => ({ poi_id: `osm:node:${id}`, provider: 'osm', osm_type: 'node', osm_id: id,
  name, latitude: 22.5, longitude: 88.35, category: 'cafe', cuisine: 'regional;indian', source_url: `https://www.openstreetmap.org/node/${id}` });
function fixture() {
  return { schema_version: 'food-osm-1', license: 'ODbL-1.0', attribution_url: 'https://www.openstreetmap.org/copyright',
    snapshot_id: 's', snapshot_date: '2026-09-17T00:00:00Z', pois: [poi(), poi(2, null)],
    coverage: [{ pandal_id: 'p', status: 'snapshot', radius_m: 600 }],
    associations: [1, 2].map(i => ({ pandal_id: 'p', poi_id: `osm:node:${i}`, provider: 'osm', distance_m: 100 / i, source_snapshot: 's' })) };
}
const legacy = () => ({ pandals: [{ pandal_id: 'p' }], groups: new Map([['p', [{ id: 'googleID', name: null, url: 'https://www.google.com/maps/search/?api=1&query=restaurant&query_place_id=googleID' }]]]) });
const policy = (provider, google_links = []) => ({ schema_version: 'food-provider-1', provider, initial_display_limit: 15, google_links });
test('OSM handoff pins independent coordinates without claiming Google identity', () => {
  const url = new URL(osmMapsURL(poi()));
  assert.equal(url.searchParams.get('query'), '22.5000000,88.3500000');
  assert.equal(url.searchParams.get('key'), null); assert.equal(url.searchParams.get('query_place_id'), null);
  assert.equal(new URL(osmMapsURL(poi(), 'verified')).searchParams.get('query_place_id'), 'verified');
  assert.equal(osmMapsURL({ ...poi(), latitude: NaN }), null);
});
test('chain, independent, special-character and missing names never broaden coordinate fallback', () => {
  for (const name of ['Taco Bell', 'Local Cafe', 'খাবার & Café / #1', null]) {
    const url = new URL(osmMapsURL(poi(1, name)));
    assert.equal(url.searchParams.get('query'), '22.5000000,88.3500000');
    assert.equal(url.searchParams.has('key'), false);
  }
  const link = { poi_id: 'osm:node:1', place_id: 'fixture', status: 'suggested',
    identity_source: 'https://example.org', verified_at: '2026-09-19T00:00:00Z' };
  assert.throws(() => combineFood(legacy(), fixture(), policy('hybrid', [link])));
});
test('OSM mode retains useful names/categories/cuisine, sorted distance; unnamed remains unnamed', () => {
  const result = combineFood(legacy(), fixture(), policy('osm'));
  const rows = result.groups.get('p'); assert.equal(rows.length, 2); assert.equal(rows[0].name, null);
  assert.equal(rows[1].name, 'মিত্র Cafe & Food'); assert.equal(rows[1].cuisine, 'regional;indian');
  assert.equal(rows[1].category, 'cafe'); assert.equal(result.displayLimit, 15);
  assert.equal(result.osmCoverage.has('p'), true);
});
test('Google rollback and missing supplemental dataset retain original contract', () => {
  for (const config of [policy('google'), null]) assert.equal(combineFood(legacy(), fixture(), config).groups.get('p')[0].id, 'googleID');
  assert.equal(combineFood(legacy(), null, policy('hybrid')).groups.get('p')[0].id, 'googleID');
});
test('hybrid preserves unresolved Google records without fuzzy merging', () => {
  assert.equal(combineFood(legacy(), fixture(), policy('hybrid')).groups.get('p').length, 3);
  const link = { poi_id: 'osm:node:1', place_id: 'googleID', identity_source: 'https://example.org/identity', verified_at: '2026-09-17T00:00:00Z' };
  const rows = combineFood(legacy(), fixture(), policy('hybrid', [link])).groups.get('p');
  assert.equal(rows.length, 2); assert.equal(new URL(rows[1].url).searchParams.get('query_place_id'), 'googleID');
  assert.throws(() => combineFood(legacy(), fixture(), policy('hybrid', [link, link])), /Ambiguous/);
});
test('invalid provenance, wrong snapshot, malformed catchment fail rather than relabel Google content', () => {
  const data = fixture(); data.pois[0].provider = 'google';
  assert.throws(() => combineFood(legacy(), data, policy('osm')), /Invalid OSM/);
  const data2 = fixture(); data2.associations[0].source_snapshot = 'wrong';
  assert.throws(() => combineFood(legacy(), data2, policy('osm')), /Invalid OSM/);
  const data3 = fixture(); data3.associations[0].distance_m = 601;
  assert.throws(() => combineFood(legacy(), data3, policy('osm')), /catchment/);
});

const mapped = (id = 'p') => ({ pandal_id: id, name: id, latitude: 22.5, longitude: 88.35, coordinate_source: 'https://www.openstreetmap.org/node/123' });
test('presentation filters anonymous/Google rows without deleting retained associations', () => {
  const combined = combineFood(legacy(), fixture(), policy('hybrid'));
  const before = JSON.stringify([...combined.groups]);
  const visible = publicFood(combined, mapped());
  assert.equal(visible.named_public_count, 1); assert.equal(visible.historical_google_association_count, 1);
  assert.equal(visible.rows[0].name, 'মিত্র Cafe & Food'); assert.equal(visible.rows[0].category, 'cafe');
  assert.equal(visible.rows[0].cuisine, 'regional;indian'); assert.equal(visible.rows[0].distance, 100);
  assert.ok(visible.rows[0].url.startsWith('https://www.google.com/maps/search/?'));
  assert.equal(JSON.stringify([...combined.groups]), before);
});
test('public named list caps at twenty; stable distance/name/ID ordering and distinct counts', () => {
  const rows = Array.from({ length: 35 }, (_, i) => ({ id: `osm:node:${i + 1}`, provider: 'osm', name: `Cafe ${i}`, distance: 100 - i }));
  const data = { pandals: [mapped()], groups: new Map([['p', [...rows, rows[0]]]]) };
  const result = publicFood(data, mapped());
  assert.equal(INITIAL_FOOD_LIMIT, 12); assert.equal(MAX_FOOD_LIMIT, 20);
  assert.equal(result.named_public_count, 20); assert.equal(result.named_snapshot_count, 35);
  assert.equal(result.rows[0].id, 'osm:node:35'); assert.equal(result.rows.at(-1).id, 'osm:node:16');
  assert.equal(foodGeography(data)[0].count, 35);
  rows[0].distance = rows[1].distance = 0; rows[0].name = ' zed '; rows[1].name = 'Alpha';
  assert.equal(publicFood(data, mapped()).rows[0].id, rows[1].id);
});
test('geography counts shared POIs per pandal, excludes unmapped, and does not rank by count', () => {
  const row = { id: 'osm:node:1', provider: 'osm', name: 'Shared cafe', distance: 100 };
  const data = { pandals: [mapped('z'), mapped('a'), { pandal_id: 'unmapped' }], groups: new Map([['a', [row, row]], ['z', [row]]]) };
  assert.deepEqual(foodGeography(data).map(x => [x.pandal.pandal_id, x.count]), [['a', 1], ['z', 1]]);
});
test('sparse mapped pandal gets a keyless neighbourhood search, never a fabricated place ID', () => {
  const url = new URL(pandalFoodURL(mapped()));
  assert.equal(url.searchParams.get('query'), 'restaurants near 22.5000000,88.3500000');
  assert.equal(url.searchParams.get('api'), '1'); assert.equal(url.searchParams.get('query_place_id'), null);
  assert.equal(url.searchParams.get('key'), null);
  assert.equal(pandalFoodURL({ ...mapped(), coordinate_source: null }), null);
  assert.equal(pandalFoodURL({ pandal_id: 'missing' }), null);
  assert.equal(pandalFoodURL({ ...mapped(), latitude: 91 }), null);
});
test('empty, placeholder or non-OSM names cannot become public food rows', () => {
  const rows = ['', ' ', 'Unknown', 'Unnamed', '???', 'Restaurant on Google Maps'].map((name, i) => ({ id: `osm:node:${i + 1}`, provider: 'osm', name, distance: 1 }));
  rows.push({ id: 'google', provider: 'google', name: 'Not an accepted durable source here', distance: 1 });
  assert.equal(publicFood({ groups: new Map([['p', rows]]) }, mapped()).named_public_count, 0);
});
