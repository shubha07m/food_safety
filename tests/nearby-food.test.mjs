import test from 'node:test';
import assert from 'node:assert/strict';
import { combineFood, osmMapsURL } from '../site/nearby-food.mjs';

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
test('OSM handoff encodes independent name/location without API or invented Google ID', () => {
  const url = new URL(osmMapsURL(poi()));
  assert.equal(url.searchParams.get('query'), 'মিত্র Cafe & Food 22.5000000,88.3500000');
  assert.equal(url.searchParams.get('key'), null); assert.equal(url.searchParams.get('query_place_id'), null);
  assert.equal(new URL(osmMapsURL(poi(), 'verified')).searchParams.get('query_place_id'), 'verified');
  assert.equal(osmMapsURL({ ...poi(), latitude: NaN }), null);
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
