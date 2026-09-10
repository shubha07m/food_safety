import test from 'node:test';
import assert from 'node:assert/strict';
import { applyRoute, recordRoute } from '../site/routes.mjs';
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
test('brand and bilingual disclosure preserve tracker identity without blanket no-model claims', () => {
  const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.match(html, /<h1 id="headline">THE BENGAL<br><em>FOODPATH/);
  assert.match(html, /class="module-title">West Bengal Food Safety Evidence Tracker/);
  const policy = readFileSync(new URL('../site/methodology.html', import.meta.url), 'utf8');
  assert.doesNotMatch(policy, /LLM calls are disabled by default/);
  const copy = readFileSync(new URL('../site/phase1.mjs', import.meta.url), 'utf8');
  assert.match(copy, /may publish automatically/);
  assert.match(copy, /স্বয়ংক্রিয়ভাবে প্রকাশযোগ্য/);
});
