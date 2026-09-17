import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { parsePlaces, searchPandals, featuredPandals, nextOption, mapsURL, normalize, discoveryState } from '../site/puja.mjs';
import { areaMarkers, browserMapKey, pandalMarkers } from '../site/map-host.mjs';
import { scriptURL, safeMarkers, boot } from '../site/google-map.mjs';
import { text } from '../site/foodpath-copy.mjs';

const fixture = () => ({ schema_version: 'places-1', association_semantics: 'historical_discovery_not_current_proximity',
  pandals: [{ pandal_id: 'bagbazar', name: 'Bagbazar Sarbojanin', name_bn: 'বাগবাজার সর্বজনীন', area: 'North Kolkata', enabled: true }],
  restaurants: [{ place_id: 'fixture_ID', curated: null }],
  associations: [{ pandal_id: 'bagbazar', place_id: 'fixture_ID', observed_at: '2026-09-15T00:00:00Z', provenance: 'google_places_local_radius_match' }] });
test('autocomplete list is anchored below its input rather than over typed text', () => {
  const html = readFileSync('site/index.html', 'utf8'); const css = readFileSync('site/styles.css', 'utf8');
  assert.match(html, /class="pandal-combobox"[\s\S]*id="pandal-search"[\s\S]*id="pandal-options"/);
  assert.match(css, /\.pandal-combobox\s*\{[^}]*position:\s*relative/);
  assert.match(css, /#pandal-options\s*\{[^}]*top:\s*calc\(100% \+ 7px\)/);
  assert.doesNotMatch(css, /#pandal-options\s*\{[^}]*top:\s*88px/);
});
test('umbrella homepage has two first-class modules and bounded analytics disclosure', () => {
  const html = readFileSync('site/index.html', 'utf8');
  for (const id of ['headline', 'food-safety', 'puja', 'geography', 'evidence', 'evidence-analytics', 'selected-pandal']) assert.ok(html.includes(`id="${id}"`));
  assert.match(html, /role="combobox"/); assert.match(html, /aria-controls="pandal-options"/);
  assert.match(html, /<details id="evidence-analytics"/);
});
test('search English Bengali areas case and whitespace locally', () => {
  const { index } = parsePlaces(fixture());
  for (const q of ['bag', 'BAGBAZAR', '  north   KOLKATA ', 'বাগবাজার', 'সর্বজনীন']) assert.equal(searchPandals(index, q).length, 1);
  assert.equal(searchPandals(index, 'unlisted').length, 0);
  assert.equal(normalize(' A   B '), 'a b');
});
test('published pandal catalog extends search without changing Places associations', () => {
  const catalog = { records: [{ pandal_id: 'bagbazar', name: 'Bagbazar Sarbojanin', name_bn: 'বাগবাজার সর্বজনীন', aliases: ['Baghbazar'], area: 'Bagbazar', neighborhood: 'North Kolkata', city: 'Kolkata', featured: true }] };
  const parsed = parsePlaces(fixture(), catalog);
  assert.equal(searchPandals(parsed.index, 'baghbazar').length, 1);
  assert.equal(searchPandals(parsed.index, 'north kolkata').length, 1);
  assert.equal(parsed.groups.get('bagbazar').length, 1);
});
test('thousands of pandals do not become thousands of cards or options', () => {
  const data = fixture();
  data.pandals = Array.from({ length: 5000 }, (_, i) => ({ ...data.pandals[0], pandal_id: `p${i}`, name: `Pandal ${i}` }));
  const parsed = parsePlaces(data);
  assert.equal(searchPandals(parsed.index, 'pandal').length, 8);
  assert.equal(featuredPandals(parsed.pandals, parsed.pandals.map(p => p.pandal_id)).length, 6);
  assert.equal(featuredPandals(parsed.pandals, ['not-listed']).length, 0);
});
test('keyboard cursor wraps and Escape clears selection', () => {
  assert.equal(nextOption('ArrowDown', -1, 8), 0);
  assert.equal(nextOption('ArrowUp', -1, 8), 7);
  assert.equal(nextOption('ArrowDown', 7, 8), 0);
  assert.equal(nextOption('Escape', 3, 8), -1);
  assert.equal(nextOption('ArrowDown', -1, 0), -1);
});
test('restaurant handoff uses both query fields, no raw ID label or invented names', () => {
  const data = parsePlaces(fixture()); const r = data.groups.get('bagbazar')[0];
  assert.equal(r.name, null); assert.equal(r.at, '2026-09-15');
  const url = new URL(mapsURL(r.id));
  assert.equal(url.searchParams.get('query'), 'restaurant'); assert.equal(url.searchParams.get('query_place_id'), r.id);
  assert.equal(mapsURL('bad&key=value'), null);
  assert.match(readFileSync('site/puja.mjs', 'utf8'), /row.name \|\| text\('Restaurant on Google Maps'\)/);
});
test('only independent names and duplicate-free historical associations survive', () => {
  const data = fixture(); data.associations.push({ ...data.associations[0] });
  data.restaurants[0].curated = { name: 'Independently curated', independent_source: 'https://example.org/menu', source_kind: 'independently_curated' };
  assert.equal(parsePlaces(data).groups.get('bagbazar').length, 1);
  assert.equal(parsePlaces(data).groups.get('bagbazar')[0].name, 'Independently curated');
  data.restaurants[0].curated.independent_source = 'https://maps.google.com/';
  assert.equal(parsePlaces(data).groups.get('bagbazar')[0].name, null);
});
test('restaurant state distinguishes not run, current zero, current links, and stale', () => {
  const p = { pandal_id: 'p', latitude: 22.5, longitude: 88.3 };
  const current = { pandal_id: 'p', observed_at: '2026-09-16T00:00:00Z', expires_at: '2026-09-23T00:00:00Z', candidates_returned: 0, result_limit_reached: false };
  assert.equal(discoveryState(p, null, [], new Date('2026-09-17T00:00:00Z')), 'not_run');
  assert.equal(discoveryState(p, current, [], new Date('2026-09-17T00:00:00Z')), 'current_zero');
  assert.equal(discoveryState(p, current, [{ id: 'x' }], new Date('2026-09-17T00:00:00Z')), 'current_nonzero');
  assert.equal(discoveryState(p, current, [], new Date('2026-09-24T00:00:00Z')), 'stale');
  assert.equal(discoveryState({ pandal_id: 'q' }, null, [], new Date()), 'unavailable');
});
test('reject restaurant coordinates, reviews, ratings, and durable exact distances', () => {
  for (const key of ['latitude', 'longitude', 'rating', 'reviews', 'displayName']) {
    const data = fixture(); data.restaurants[0][key] = 'restricted'; assert.throws(() => parsePlaces(data));
  }
  const data = fixture(); data.associations[0].distance_m = 42; assert.throws(() => parsePlaces(data));
});
test('Maps loader requests JavaScript only, not Places, and stays browser-only', () => {
  const url = new URL(scriptURL('AIza' + 'a'.repeat(35), 'bn'));
  assert.equal(url.hostname, 'maps.googleapis.com'); assert.equal(url.searchParams.get('language'), 'bn');
  assert.equal(url.searchParams.get('v'), 'quarterly'); assert.equal(url.searchParams.has('libraries'), false);
  assert.equal(url.searchParams.get('auth_referrer_policy'), 'origin');
  assert.throws(() => scriptURL(''));
  const host = readFileSync('site/map-host.mjs', 'utf8');
  assert.ok(host.indexOf("button.addEventListener('click'") < host.indexOf("document.createElement('iframe')"));
  assert.doesNotMatch(host, /GOOGLE_MAPS_API_KEY|searchNearby|placeDetails/);
});
test('browser map config enables only a valid public browser key and fails safely', async () => {
  const key = 'AIza' + 'a'.repeat(35);
  assert.equal(await browserMapKey(async () => ({ ok: true, json: async () => ({ browser_key: key }) })), key);
  assert.equal(await browserMapKey(async () => ({ ok: false })), '');
  assert.equal(await browserMapKey(async () => ({ ok: true, json: async () => ({ browser_key: 'server-key' }) })), '');
});
test('map plots only eligible area anchors and curated pandals, no restaurant layer', () => {
  const row = { reported_fact: { area: 'Area' }, derived_context: { location_reviewed: true, location_precision: 'neighborhood', latitude: 22.6, longitude: 88.36, location_source: 'https://www.openstreetmap.org/' } };
  assert.equal(areaMarkers([row, row])[0].count, 2);
  assert.equal(areaMarkers([{ ...row, derived_context: { ...row.derived_context, location_precision: 'district' } }]).length, 0);
  assert.equal(pandalMarkers(fixture().pandals).length, 0);
  assert.equal(pandalMarkers([{ pandal_id: 'verified', name: 'Verified', latitude: 22.6, longitude: 88.36, coordinate_source: 'https://example.org/source' }]).length, 1);
  assert.equal(safeMarkers([{ kind: 'restaurant', id: 'x', label: 'x', lat: 22, lng: 88 }]).length, 0);
});
test('every published map-ready pandal becomes a marker', () => {
  const catalog = JSON.parse(readFileSync('site/data/pandals.json', 'utf8'));
  const markers = pandalMarkers(catalog.records);
  assert.equal(markers.length, catalog.coverage.map_ready_count);
  assert.equal(new Set(markers.map(marker => marker.id)).size, markers.length);
});
test('map document has isolated CSP and parent keeps self-only scripts', () => {
  assert.match(readFileSync('site/index.html', 'utf8'), /script-src 'self';/);
  assert.match(readFileSync('site/google-map.html', 'utf8'), /https:\/\/maps.googleapis.com/);
  assert.doesNotMatch(readFileSync('site/google-map.html', 'utf8'), /script-src[^;]*'unsafe-inline'/);
  assert.match(readFileSync('site/_headers', 'utf8'), /\/google-map.html\n  ! Content-Security-Policy/);
  const map = readFileSync('site/google-map.html', 'utf8');
  assert.match(map, /id="pandals-layer" checked/); assert.doesNotMatch(map, /id="areas-layer" checked/);
  assert.match(readFileSync('.env.example', 'utf8'), /^GOOGLE_MAPS_BROWSER_KEY=$/m);
  assert.doesNotMatch(readFileSync('.gitignore', 'utf8'), /^site\/maps-config.json$/m);
  const config = JSON.parse(readFileSync('site/maps-config.json', 'utf8'));
  assert.deepEqual(Object.keys(config), ['browser_key']);
  assert.equal(typeof config.browser_key, 'string');
  assert.ok(config.browser_key === '' || /^AIza[A-Za-z0-9_-]{35}$/.test(config.browser_key));
});
test('Bengali new UI translations exist without translating evidence', () => {
  for (const key of ['Puja FoodPath', 'Search for a Puja pandal', 'Restaurant on Google Maps', 'Food Safety Evidence', 'Load Google map']) assert.match(text(key, 'bn'), /[\u0980-\u09ff]/);
});
test('mock Maps boot filters origins and loads once without network', () => {
  const messages = []; const scripts = []; const listeners = {};
  const parent = { postMessage: m => messages.push(m) };
  const win = { parent, location: { origin: 'https://example.org' }, addEventListener: (event, cb) => { listeners[event] = cb; } };
  const doc = { createElement: () => ({}), head: { append: script => scripts.push(script) }, getElementById: () => ({}) };
  boot(win, doc); assert.equal(messages[0].type, 'foodpath-map-ready');
  boot(win, doc); assert.equal(messages.length, 1);
  const message = { type: 'foodpath-map-data', key: 'AIza' + 'b'.repeat(35), language: 'en', markers: [] };
  listeners.message({ origin: 'https://attacker.invalid', source: parent, data: message }); assert.equal(scripts.length, 0);
  listeners.message({ origin: win.location.origin, source: parent, data: message });
  listeners.message({ origin: win.location.origin, source: parent, data: message }); assert.equal(scripts.length, 1);
  scripts[0].onerror(); assert.equal(messages.at(-1).type, 'foodpath-map-error');
  listeners.message({ origin: win.location.origin, source: parent, data: message });
  assert.equal(scripts.length, 1);
});
test('mock map fits all pandals and focuses mapped selection without false fallback focus', () => {
  const messages = []; const listeners = {}; const elements = new Map(); let features; let style; let click; let info; const centers = []; const zooms = []; const bounds = [];
  const node = () => ({ children: [], checked: true, append(...items) { this.children.push(...items); }, addEventListener(type, cb) { this[type] = cb; } });
  const doc = { createElement: node, head: node(), getElementById(id) { if (!elements.has(id)) elements.set(id, node()); return elements.get(id); } };
  const parent = { postMessage: m => messages.push(m) };
  const win = { parent, location: { origin: 'https://example.org' }, addEventListener: (e, cb) => { listeners[e] = cb; }, google: { maps: {
    Map: class { constructor() { this.data = { forEach() {}, remove() {}, addGeoJson(f) { features = f.features; }, setStyle(s) { style = s; }, addListener(e, cb) { click = cb; } }; } fitBounds(b) { bounds.push(b.points); } setCenter(c) { centers.push(c); } setZoom(z) { zooms.push(z); } },
    LatLngBounds: class { constructor() { this.points = []; } extend(p) { this.points.push(p); } }, SymbolPath: { CIRCLE: 'circle' },
    InfoWindow: class { setContent(c) { info = c; } setPosition() {} open() {} },
  } } };
  boot(win, doc);
  listeners.message({ origin: win.location.origin, source: parent, data: { type: 'foodpath-map-data', key: 'AIza' + 'f'.repeat(35), language: 'en', markers: [
    { id: 'area-0', kind: 'area', label: '<img onerror=bad>', lat: 22.5, lng: 88.3, count: 2 },
    { id: 'pandal-bagbazar', kind: 'pandal', label: 'Bagbazar', lat: 22.6, lng: 88.3 },
    { id: 'pandal-chetla', kind: 'pandal', label: 'Chetla', lat: 22.51, lng: 88.33 },
  ] } });
  win.foodpathMapLoaded();
  assert.equal(features.length, 3); assert.equal(messages.at(-1).type, 'foodpath-map-loaded');
  assert.equal(bounds.at(-1).length, 2);
  listeners.message({ origin: win.location.origin, source: parent, data: { type: 'foodpath-map-focus', id: 'pandal-chetla' } });
  assert.deepEqual(centers.at(-1), { lat: 22.51, lng: 88.33 }); assert.equal(zooms.at(-1), 14);
  listeners.message({ origin: win.location.origin, source: parent, data: { type: 'foodpath-map-focus', id: null } });
  assert.equal(bounds.at(-1).length, 2);
  const feature = f => ({ getProperty: k => f.properties[k], getId: () => f.id });
  assert.equal(style(feature(features[0])).icon.path, 'circle');
  assert.notEqual(style(feature(features[1])).icon.path, 'circle');
  elements.get('areas-layer').checked = false;
  assert.equal(style(feature(features[0])).visible, false);
  click({ feature: feature(features[0]), latLng: {} });
  assert.equal(info.children[0].textContent, '<img onerror=bad>');
  info.children[2].click(); assert.equal(messages.at(-1).id, 'area-0');
  click({ feature: feature(features[1]), latLng: {} });
  info.children[2].click(); assert.equal(messages.at(-1).id, 'pandal-bagbazar');
});
