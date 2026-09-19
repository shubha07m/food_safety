import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parseRegions, regionFromURL, regionURL, scopeFood } from '../site/regions.mjs';
import { featuredPandals, searchPandals } from '../site/puja.mjs';
import { foodGeography, publicFood, pandalFoodURL } from '../site/nearby-food.mjs';
import { pandalMarkers } from '../site/map-host.mjs';
import { recordRoute, safetyRoute, applyRoute } from '../site/routes.mjs';

const region = (id, country = 'IN') => ({ region_id: id, label: id, country_code: country, food_provider_mode: 'osm',
  default_map_center: { lat: 37, lng: -120 }, default_map_zoom: 6, food_data: `data/food_${id}.json`, provider_data: `data/provider_${id}.json` });
const registry = parseRegions({ schema_version: 'puja-regions-1', default_region: 'kolkata', regions: [region('kolkata'), region('california', 'US')] });
const p = (id, region_id = 'kolkata') => ({ pandal_id: id, region_id, name: id, latitude: 37, longitude: -120, coordinate_source: 'https://www.openstreetmap.org/node/1' });
const rows = n => Array.from({ length: n }, (_, i) => ({ id: `osm:node:${i + 1}`, name: `Food ${i}`, provider: 'osm', distance: i + 10 }));
function data() {
  const pandals = [p('Ekdalia'), p('Bay Area Puja', 'california'), { ...p('Unmapped', 'california'), latitude: null, longitude: null }];
  return { pandals, index: pandals.map(p => ({ p, query: p.name.toLowerCase() })),
    groups: new Map([['Ekdalia', rows(3)], ['Bay Area Puja', rows(4)]]), discoveries: new Map() };
}
test('region default, unknown and Bengali URLs are controlled', () => {
  for (const url of ['', '?region=kolkata', '?region=unknown']) assert.equal(regionFromURL(url, registry).region_id, 'kolkata');
  assert.equal(regionFromURL('?region=california&lang=bn', registry).region_id, 'california');
  assert.throws(() => parseRegions({ ...registry, regions: [...registry.regions, registry.regions[0]] }), /Invalid/);
});
test('region registry rejects remote/arbitrary food URLs', () => {
  assert.throws(() => parseRegions({ ...registry, regions: [{ ...registry.regions[0], food_data: 'https://example.org/food' }] }), /Invalid/);
});
test('region switch removes incompatible selection but preserves language and route parameters', () => {
  const url = regionURL('https://example.org/?pandal=Ekdalia&lang=bn', 'california', [p('Bay Area Puja', 'california')]);
  assert.equal(url.searchParams.get('pandal'), null); assert.equal(url.searchParams.get('lang'), 'bn');
  assert.equal(url.searchParams.get('region'), 'california');
});
test('scoped search, named counts, markers and geography exclude other regions', () => {
  const scoped = scopeFood(data(), registry.regions[1], registry.default_region);
  assert.equal(scoped.pandals.length, 2);
  assert.equal(searchPandals(scoped.index, 'Ekdalia').length, 0);
  assert.equal(searchPandals(scoped.index, 'Bay Area').length, 1);
  assert.equal(scoped.groups.has('Ekdalia'), false);
  assert.equal(foodGeography(scoped).length, 1);
  assert.equal(foodGeography(scoped)[0].count, 4);
  assert.deepEqual(pandalMarkers(scoped.pandals).map(m => m.id), ['pandal-Bay Area Puja']);
});
test('featured requires sourced coordinates, a meaningful OSM name and curated eligibility', () => {
  const d = data(); d.pandals.push(p('Sparse'), p('Google only'));
  d.groups.set('Google only', [{ id: 'g', name: null, provider: 'google' }]);
  assert.deepEqual(featuredPandals(d, ['Sparse', 'Google only', 'Unmapped', 'Ekdalia']).map(p => p.pandal_id), ['Ekdalia']);
  const scoped = scopeFood(d, registry.regions[1], registry.default_region);
  assert.deepEqual(featuredPandals(scoped, ['Ekdalia', 'Bay Area Puja']).map(p => p.pandal_id), ['Bay Area Puja']);
});
test('featured prefers three named matches when enough curated entries qualify and caps at six', () => {
  const d = { pandals: Array.from({ length: 10 }, (_, i) => p(`P${i}`)), groups: new Map() };
  d.pandals.forEach((p, i) => d.groups.set(p.pandal_id, rows(i === 0 ? 1 : 3)));
  const result = featuredPandals(d, d.pandals.map(p => p.pandal_id));
  assert.equal(result.length, 6); assert.equal(result.some(p => p.pandal_id === 'P0'), false);
});
test('sparse California mapped case has one URL, unmapped case none', () => {
  const mapped = p('Sparse', 'california');
  assert.equal(publicFood({ groups: new Map() }, mapped).named_public_count, 0);
  assert.ok(new URL(pandalFoodURL(mapped)).searchParams.get('query').includes('-120'));
  assert.equal(pandalFoodURL({ ...mapped, latitude: null, longitude: null }), null);
});
test('Food Safety and event URLs ignore Puja region and retain their independent routes', () => {
  for (const query of ['?module=safety&region=california', '?module=safety&lang=bn']) {
    assert.equal(safetyRoute(query), true); assert.equal(regionFromURL(query, registry).region_id, 'kolkata');
  }
  assert.equal(recordRoute('?event=WBFS-x&region=california&lang=bn'), true);
});
test('Puja banner excludes evidence wording while evidence routes retain it', () => {
  const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.match(html, /status-strip puja-only[^>]*><span>PUJA NEIGHBOURHOODS/);
  assert.match(html, /evidence-banner[^>]*hidden/);
  assert.match(html, /Inclusion is not a finding of wrongdoing/);
  const banner = { toggleAttribute: (_, yes) => { banner.hidden = yes; } };
  const root = { getElementById: () => ({}), querySelector: () => banner };
  applyRoute(root, '?region=california'); assert.equal(banner.hidden, true);
  applyRoute(root, '?module=safety'); assert.equal(banner.hidden, false);
  applyRoute(root, '?event=WBFS-x'); assert.equal(banner.hidden, false);
});
