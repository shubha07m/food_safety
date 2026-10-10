// A boolean tab-session receipt only, never an identifier or location record.
export async function visitCount({ fetcher = fetch, storage } = {}) {
  let first;
  try { storage ||= globalThis.sessionStorage; first = storage.getItem('foodpath-visit-v1') !== 'sent'; if (first) storage.setItem('foodpath-visit-v1', 'sent'); }
  catch { first = false; } // No persistence available: read-only avoids reload inflation.
  const read = async method => { try {
    const response = await fetcher('/api/visits', {
      method, credentials: 'omit', cache: 'no-store',
      ...(method === 'POST' ? { headers: { 'Content-Type': 'application/json', 'X-FoodPath-Visit': '1' }, body: '{}' } : {}),
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) return null;
    const data = await response.json();
    return Number.isSafeInteger(data.count) && data.count >= 0 ? data.count : null;
  } catch { return null; } };
  const count = await read(first ? 'POST' : 'GET');
  // Never retry an uncertain write. One read can still display the aggregate.
  return count === null && first ? read('GET') : count;
}
export function visitCopy(count, bn = false) {
  const n = count.toLocaleString(bn ? 'bn-BD' : 'en-US');
  return { label: bn ? `${n} সাইট ভিজিট — গণনা চলছে` : `${n} site visits and counting`,
    description: bn ? 'আনুমানিক ব্রাউজার-ট্যাব সেশনের সংখ্যা; স্বতন্ত্র মানুষের সংখ্যা নয়'
      : 'Approximate counted browser-tab sessions, not unique people' };
}
export function initVisits(doc = document, { countVisit = visitCount, schedule = setTimeout } = {}) {
  const node = doc.getElementById('site-visits'); if (!node) return;
  const start = () => {
    if (doc.visibilityState === 'hidden') return;
    doc.removeEventListener('visibilitychange', start);
    schedule(async () => {
      if (doc.visibilityState === 'hidden') { doc.addEventListener('visibilitychange', start); return; }
      let count = null;
      try { count = await countVisit(); } catch { /* Storage may be unavailable. */ }
      if (count !== null) { const copy = visitCopy(count, doc.documentElement.lang === 'bn'); node.textContent = copy.label; node.title = copy.description; node.hidden = false; }
    }, 1500);
  };
  if (doc.visibilityState === 'hidden') doc.addEventListener('visibilitychange', start); else start();
}
