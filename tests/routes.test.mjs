import test from 'node:test';
import assert from 'node:assert/strict';
import { applyRoute, recordRoute, safetyRoute } from '../site/routes.mjs';
import { readFileSync } from 'node:fs';

for (const lang of ['', '&lang=bn']) {
  test(`detail and back route isolate dashboard: ${lang || 'English'}`, () => {
    const elements = { 'dashboard-view': { hidden: false }, 'record-detail': { hidden: true } };
    const root = { getElementById: id => elements[id] };
    assert.equal(applyRoute(root, `?event=WBFS-aaaaaaaaaaaa${lang}`), true);
    assert.equal(elements['dashboard-view'].hidden, true);
    assert.equal(elements['record-detail'].hidden, false);
    assert.equal(applyRoute(root, lang ? '?lang=bn' : ''), false);
    assert.equal(elements['dashboard-view'].hidden, false);
    assert.equal(elements['record-detail'].hidden, true);
  });
}
test('empty and unknown event routes must not fall through to dashboard', () => {
  assert.equal(recordRoute('?event='), true);
  assert.equal(recordRoute('?event=missing&lang=bn'), true);
  assert.equal(recordRoute('?lang=bn'), false);
});
test('Puja landing and food-safety module are separate views', () => {
  assert.equal(safetyRoute(''), false);
  assert.equal(safetyRoute('?module=safety&lang=bn'), true);
  assert.equal(safetyRoute('?module=safety&event=WBFS-x'), false);
  const classes = new Set();
  const nodes = { puja: [{ hidden: false }], safety: [{ hidden: true }] };
  const root = {
    body: { classList: { toggle: (name, yes) => yes ? classes.add(name) : classes.delete(name) } },
    getElementById: id => ({ hidden: id === 'record-detail' }),
    querySelectorAll: selector => selector === '.puja-only' ? nodes.puja : nodes.safety,
  };
  applyRoute(root, '?module=safety');
  assert.ok(classes.has('safety-route')); assert.equal(nodes.puja[0].hidden, true); assert.equal(nodes.safety[0].hidden, false);
});
test('evidence area navigation is safety-only; festival food geography is Puja-only', () => {
  const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.match(html, /class="area-summary safety-only"/);
  assert.match(html, /id="festival-food-geography" class="puja-only/);
  const safety = { hidden: false }; const puja = { hidden: false };
  const root = { getElementById: () => ({}), querySelectorAll: s => [s === '.safety-only' ? safety : puja] };
  applyRoute(root, ''); assert.equal(safety.hidden, true); assert.equal(puja.hidden, false);
  applyRoute(root, '?module=safety'); assert.equal(safety.hidden, false); assert.equal(puja.hidden, true);
});
test('brand and bilingual disclosure preserve tracker identity without blanket no-model claims', () => {
  const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.match(html, /<h1 id="headline"><span>PUJA<\/span><br>FOODPATH/);
  assert.match(html, /class="module-title">West Bengal Food Safety Evidence Tracker/);
  const policy = readFileSync(new URL('../site/methodology.html', import.meta.url), 'utf8');
  assert.doesNotMatch(policy, /LLM calls are disabled by default/);
  const copy = readFileSync(new URL('../site/phase1.mjs', import.meta.url), 'utf8');
  assert.match(copy, /may publish automatically/);
  assert.match(copy, /স্বয়ংক্রিয়ভাবে প্রকাশিত হতে পারে/);
});
