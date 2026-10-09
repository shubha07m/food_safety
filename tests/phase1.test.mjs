import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const root = new URL('../', import.meta.url);
test('bilingual lifecycle and launch-closed correction policy remain static', () => {
  const code = readFileSync(new URL('site/phase1.mjs', root), 'utf8');
  for (const text of ['How record verification works', 'নথির উৎস কীভাবে যাচাই করা হয়', 'Public Food Safety correction submissions are temporarily closed', 'সাময়িকভাবে বন্ধ রয়েছে', 'last_successful_evidence_check_at', 'ever_published']) assert.ok(code.includes(text));
  assert.doesNotMatch(code,/community_submission_url|Submission form coming shortly|issues\/new/);
  assert.doesNotMatch(readFileSync(new URL('site/pages.js', root),'utf8'),/issues\/new|template=correction|template=source_submission/);
  assert.ok(!code.includes('innerHTML'));
  assert.ok(!code.includes('forms.gle/fake'));
  const map = readFileSync(new URL('site/geography.mjs', root), 'utf8');
  assert.ok(!map.includes('googleapis'));
});
test('public lifecycle metrics reconcile to active rows', () => {
  const data = JSON.parse(readFileSync(new URL('site/data/events.json', root)));
  const summary = JSON.parse(readFileSync(new URL('site/data/lifecycle.json', root)));
  assert.equal(summary.active, data.records.length);
  assert.equal(summary.ever_published, summary.active + summary.non_active);
  assert.equal(summary.states.active_with_warning || 0, data.records.filter(r => r.publication_status === 'active_with_warning').length);
});
