import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { regionalSearches, foodView } from '../site/regional-food.mjs';

const registry = JSON.parse(readFileSync(new URL('../site/data/regions.json', import.meta.url)));
const ca = registry.regions.find(r => r.region_id === 'california');
const kolkata = registry.regions.find(r => r.region_id === 'kolkata');
test('four California regional searches are keyless handoffs, not restaurant records', () => {
  const links = regionalSearches(ca);
  assert.deepEqual(links.map(x => x.area_id), ['bay-area', 'southern-california', 'sacramento', 'all-california']);
  for (const row of links) {
    const url = new URL(row.url);
    assert.equal(row.type, 'regional_food_search');
    assert.equal(url.searchParams.get('query'), row.query);
    assert.equal(url.searchParams.get('api'), '1');
    assert.deepEqual([...url.searchParams.keys()], ['api', 'query']);
    assert.equal(row.poi_id, undefined);
    assert.equal(row.place_id, undefined);
  }
  assert.equal(regionalSearches(kolkata).length, 0);
});
test('regional food view is shareable, California-only and compatible with Bengali UI', () => {
  assert.equal(foodView('?region=california&view=bengali-food&lang=bn', ca), 'bengali-food');
  assert.equal(foodView('?view=bengali-food', kolkata), 'puja');
  assert.equal(foodView('?view=unknown', ca), 'puja');
  assert.equal(foodView('', ca), 'puja');
});
test('regional handoffs encode special characters and reject substituted destinations', () => {
  const query = 'Bengali sweets & café / California';
  const row = { ...ca.regional_food_searches[0], query,
    maps_url: `https://www.google.com/maps/search/?${new URLSearchParams({api:'1', query})}` };
  assert.equal(new URL(regionalSearches({...ca, regional_food_searches:[row]})[0].url).searchParams.get('query'), query);
  assert.throws(() => regionalSearches({...ca, regional_food_searches:[{...row, maps_url:'https://example.org'}]}));
});
