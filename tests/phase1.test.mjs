import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const root = new URL('../', import.meta.url);
test('bilingual lifecycle and private form integration remain static', () => {
  const code = readFileSync(new URL('site/phase1.mjs', root), 'utf8');
  for (const text of ['How record verification works', 'নথির উৎস কীভাবে যাচাই করা হয়', 'community_submission_url', 'Submission form coming shortly', 'last_successful_evidence_check_at', 'ever_published']) assert.ok(code.includes(text));
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
