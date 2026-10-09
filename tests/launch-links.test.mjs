import test from 'node:test';
import assert from 'node:assert/strict';
import { pujaLink } from '../site/global-puja.mjs';
import { localizedURL } from '../site/locale.mjs';
import { recordRoute, safetyRoute } from '../site/routes.mjs';

test('new-origin Puja sharing preserves all five regions, stable IDs and Bengali', () => {
  for (const region of ['kolkata', 'california', 'london', 'toronto', 'melbourne']) {
    const url = new URL(pujaLink({ region_id: region, pandal_id: 'existing-stable-id' }, 'https://foodpath.nemoneek.com', 'bn'));
    assert.equal(url.origin, 'https://foodpath.nemoneek.com');
    assert.equal(url.searchParams.get('region'), region);
    assert.equal(url.searchParams.get('pandal'), 'existing-stable-id');
    assert.equal(url.searchParams.get('lang'), 'bn');
  }
});
test('new-origin safety/event and language links retain existing route semantics', () => {
  const link = new URL(localizedURL('https://foodpath.nemoneek.com/?module=safety&event=WBFS-0123456789ab', 'bn'), 'https://foodpath.nemoneek.com');
  assert.equal(link.searchParams.get('event'), 'WBFS-0123456789ab');
  assert.equal(link.searchParams.get('module'), 'safety');
  assert.equal(link.searchParams.get('lang'), 'bn');
  assert.equal(recordRoute(link.search), true);
  assert.equal(safetyRoute('?module=safety&lang=bn'), true);
});
