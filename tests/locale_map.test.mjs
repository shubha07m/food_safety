import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { language, bn, localizedURL } from '../site/locale.mjs';
import { mappedRows, projection, geometryPath } from '../site/geography.mjs';
import { filterRows } from '../site/data.mjs';

test('English default, Bengali core UI, stable record URLs', () => {
  assert.equal(language, 'en');
  for (const label of ['Reported events over time', 'Area', 'Clear filters', 'Original source text', 'Disclaimer']) assert.match(bn[label], /[\u0980-\u09ff]/);
  const url = localizedURL('https://foodsafety.nemoneek.com/?event=WBFS-0123456789ab', 'bn');
  assert.match(url, /event=WBFS-0123456789ab/); assert.match(url, /lang=bn/);
  assert.doesNotMatch(localizedURL('https://foodsafety.nemoneek.com/?lang=bn', 'en'), /lang=/);
});
test('Pinned West Bengal geometry is locally served', () => {
  const feature = JSON.parse(readFileSync('site/assets/west-bengal.geojson'));
  assert.equal(feature.properties.name, 'West Bengal'); assert.equal(feature.properties.license, 'CC BY 2.5 IN');
  const path = geometryPath(feature.geometry, projection([85, 21, 90, 28], [0, 0, 300, 400]));
  assert.match(path, /^M/); assert.ok(path.length > 1000); assert.doesNotMatch(path, /NaN/);
  assert.doesNotMatch(readFileSync('site/geography.mjs', 'utf8'), /fetch\(|https?:/);
});
test('Precision determines omissions; area selection filters evidence', () => {
  const c = { latitude: 22.55, longitude: 88.35, location_precision: 'neighborhood', location_reviewed: true, location_source: 'https://www.openstreetmap.org/', normalized_area: 'Park Street' };
  const rows = [{ event_id: 'a', derived_context: c, reported_fact: {} }, { event_id: 'b', derived_context: { ...c, location_precision: 'district' }, reported_fact: {} }, { event_id: 'c', derived_context: { ...c, latitude: null }, reported_fact: {} }];
  assert.equal(mappedRows(rows).length, 1); assert.equal(rows.length - mappedRows(rows).length, 2);
  assert.equal(filterRows(mappedRows(rows), { areas: 'Park Street' })[0].event_id, 'a');
});
test('Original evidence unchanged; motion respects user preference', () => {
  const app = readFileSync('site/app.js', 'utf8');
  assert.match(app, /node\('blockquote', source.evidence_quote\)/);
  assert.match(app, /\['td', 'dd', 'q', 'blockquote'\]\.includes\(tag\) \? text/);
  assert.doesNotMatch(app, /'aria-hidden': 'true'/);
  assert.match(readFileSync('site/styles.css', 'utf8'), /prefers-reduced-motion/);
});
