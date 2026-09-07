import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { aggregate, completeness, filterOptions, filterRows, safeExternal, validateDataset } from '../site/data.mjs';

const fixture = (id, area, overrides = {}) => ({
  event_id: id, is_fixture: false, context_notice: 'Synthetic test only',
  display_summary: `Source reports an inspection in ${area}.`,
  reported_fact: { event_date: '2026-01-02', area, establishment_name: null, reported_observation: 'Synthetic inspection fixture', reported_action: null, reported_quantity: null, ...overrides.reported_fact },
  derived_context: { normalized_area: area, action_category: 'inspection / visit only', establishment_context: 'unknown', menu_context: 'unknown', business_format: 'unknown', ...overrides.derived_context },
  sources: [{ source_url: 'https://example.org/fixture', source_publisher: overrides.publisher || 'Example News', source_date: '2026-01-03' }],
  review: { all_fields_supported: true, source_context_checked: true },
  verification_status: overrides.verification_status || 'SOURCE VERIFIED',
});
const rows = [
  fixture('WBFS-aaaaaaaaaaaa', 'Example Area', { reported_fact: { establishment_name: 'Example Cafe', reported_action: 'inspected' }, derived_context: { establishment_context: 'restaurant / eatery' } }),
  fixture('WBFS-bbbbbbbbbbbb', 'Another Area', { publisher: 'Another Publisher' }),
  fixture('WBFS-cccccccccccc', 'Example Area', { derived_context: { menu_context: 'mixed', business_format: 'chain_group' }, verification_status: 'CROSS-SOURCE VERIFIED' }),
];

test('chart totals and filters agree with source rows', () => {
  const stats = aggregate(rows);
  for (const dimension of ['timeline', 'areas', 'actions', 'establishments', 'verification', 'menus', 'business_formats']) {
    assert.equal(Object.values(stats[dimension]).reduce((a, b) => a + b, 0), rows.length);
    for (const [label, count] of Object.entries(stats[dimension])) assert.equal(filterRows(rows, { [dimension]: label }).length, count);
  }
  assert.equal(stats.publishers_count, 2);
});
test('combined filters intersect correctly', () => {
  assert.equal(filterRows(rows, { areas: 'Example Area', menus: 'mixed' }).length, 1);
  assert.equal(filterRows(rows, { areas: 'Another Area', menus: 'mixed' }).length, 0);
});
test('search combines with structured filters', () => {
  assert.equal(filterRows(rows, { areas: 'Example Area' }, 'Example Cafe').length, 1);
});
test('completeness percentages derive from rows', () => {
  const coverage = completeness(rows);
  assert.deepEqual(coverage.named_establishment, { count: 1, total: 3, percentage: 33.3 });
  assert.deepEqual(coverage.cross_source, { count: 1, total: 3, percentage: 33.3 });
});
test('source composition derives from publisher fields', () => {
  assert.deepEqual(aggregate(rows).publishers, { 'Another Publisher': 1, 'Example News': 2 });
});
test('filter controls derive from available values', () => {
  assert.deepEqual(filterOptions(rows).areas, ['Another Area', 'Example Area']);
});
test('zero state has no fake metrics', () => {
  assert.equal(aggregate([]).total, 0); assert.equal(completeness([]).menu_context.percentage, 0);
});
test('unsafe source schemes and local destinations are rejected', () => {
  for (const url of ['javascript:alert(1)', 'file:///tmp/x', 'data:text/html,x', 'http://localhost', 'http://127.0.0.1', 'http://10.0.0.1', 'http://192.168.1.1', 'http://[::1]', 'https://user:pass@example.org']) assert.equal(safeExternal(url), null);
});
test('published fixture marker and invalid states fail closed', () => {
  const data = { schema_version: '1.1.0', record_count: 1, context_notice: 'Test', records: [rows[0]] };
  assert.equal(validateDataset(data), data);
  assert.throws(() => validateDataset({ ...data, records: [{ ...rows[0], is_fixture: true }] }));
  assert.throws(() => validateDataset({ ...data, records: [{ ...rows[0], verification_status: 'DISPUTED' }] }));
});
test('source-derived strings use safe DOM APIs and SVG charts are accessible', () => {
  const js = readFileSync(new URL('../site/app.js', import.meta.url), 'utf8');
  const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.equal(/innerHTML|insertAdjacentHTML|document\.write|eval\(/.test(js), false);
  assert.ok(js.includes('textContent')); assert.ok(js.includes("setAttribute('tabindex', '0')"));
  assert.ok(html.includes('role="img"')); assert.ok(html.includes('aria-label="Reported records over time'));
});
