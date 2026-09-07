import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { aggregate, dimensions, filterRows, safeExternal, validateDataset } from '../site/data.mjs';

const fixture = (id, area, menu = 'unknown') => ({
  event_id: id, is_fixture: false, context_notice: 'Synthetic test only',
  reported_fact: { event_date: '2026-01-02', area, establishment_name: null, reported_observation: 'Synthetic inspection fixture' },
  derived_context: { action_category: 'other', derived_owner_category: 'unknown', derived_menu_category: menu },
  sources: [{ source_url: 'https://example.org/fixture' }],
  review: { all_fields_supported: true, source_context_checked: true },
  verification_status: 'SOURCE VERIFIED',
});
const rows = [fixture('WBFS-aaaaaaaaaaaa', 'Example Area'), fixture('WBFS-bbbbbbbbbbbb', 'Another Area'), fixture('WBFS-cccccccccccc', 'Example Area', 'both')];

test('chart totals and click filters agree with their source rows', () => {
  const stats = aggregate(rows);
  for (const dimension of Object.keys(dimensions)) {
    assert.equal(Object.values(stats[dimension]).reduce((a, b) => a + b, 0), rows.length);
    for (const [label, count] of Object.entries(stats[dimension])) assert.equal(filterRows(rows, dimension, label).length, count);
  }
  assert.equal(stats.sources_count, 1);
  assert.equal(stats.establishments_count, 0);
});
test('zero state has no fake metrics', () => { assert.equal(aggregate([]).total, 0); assert.deepEqual(aggregate([]).timeline, {}); });
test('search intersects the selected chart', () => { assert.equal(filterRows(rows, 'areas', 'Example Area', 'synthetic').length, 2); assert.equal(filterRows(rows, 'areas', 'Example Area', 'nonexistent').length, 0); });
test('unsafe source schemes and local destinations are rejected', () => {
  for (const url of ['javascript:alert(1)', 'file:///tmp/x', 'data:text/html,x', 'http://localhost', 'http://127.0.0.1', 'http://10.0.0.1', 'http://192.168.1.1', 'http://[::1]', 'https://user:pass@example.org']) assert.equal(safeExternal(url), null);
});
test('published fixture marker and invalid states fail closed', () => {
  const data = { schema_version: '1.0.0', record_count: 1, context_notice: 'Test', records: [rows[0]] };
  assert.equal(validateDataset(data), data);
  assert.throws(() => validateDataset({ ...data, records: [{ ...rows[0], is_fixture: true }] }));
  assert.throws(() => validateDataset({ ...data, records: [{ ...rows[0], verification_status: 'DISPUTED' }] }));
});
test('source-derived strings are rendered without HTML insertion', () => {
  const js = readFileSync(new URL('../site/app.js', import.meta.url), 'utf8');
  assert.equal(/innerHTML|insertAdjacentHTML|document\.write|eval\(/.test(js), false);
  assert.ok(js.includes('textContent'));
});
