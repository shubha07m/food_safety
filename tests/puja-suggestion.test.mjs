import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { googleFormURL, showPujaSuggestion } from '../site/puja-suggestion.mjs';

test('Puja suggestion handoff accepts only published Google Form URLs', () => {
  assert.equal(googleFormURL('https://forms.gle/example123'), 'https://forms.gle/example123');
  assert.equal(googleFormURL('https://docs.google.com/forms/d/e/example/viewform'), 'https://docs.google.com/forms/d/e/example/viewform');
  for (const value of [null, '', 'https://example.org/', 'https://github.com/example/issues', 'https://docs.google.com/forms/d/e/example/edit', 'http://forms.gle/example123']) {
    assert.equal(googleFormURL(value), null);
  }
});

test('configured Puja form opens a new tab; missing config stays unavailable', () => {
  const container = {
    ownerDocument: { createElement: tag => ({ tag }) },
    replaceChildren(...children) { this.children = children; },
  };
  assert.equal(showPujaSuggestion(container, null), false);
  assert.equal(container.children, undefined);
  assert.equal(showPujaSuggestion(container, 'https://forms.gle/example123'), true);
  assert.deepEqual(container.children[0], {
    tag: 'a', className: 'text-link', textContent: 'Suggest a Puja ↗',
    href: 'https://forms.gle/example123', target: '_blank', rel: 'noopener noreferrer',
  });
  const html = readFileSync(new URL('../site/index.html', import.meta.url), 'utf8');
  assert.match(html, /Suggestion form coming shortly/);
  assert.doesNotMatch(html, /issues\/new\?template=suggest_puja/);
});
