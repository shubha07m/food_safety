// A boolean tab-session receipt only, never an identifier or location record.
export async function visitCount({ fetcher = fetch, storage } = {}) {
  let first;
  try { storage ||= globalThis.sessionStorage; first = storage.getItem('foodpath-visit-v1') !== 'sent'; if (first) storage.setItem('foodpath-visit-v1', 'sent'); }
  catch { first = false; } // No persistence available: read-only avoids reload inflation.
  try {
    const response = await fetcher('/api/visits', {
      method: first ? 'POST' : 'GET', credentials: 'omit', cache: 'no-store',
      ...(first ? { headers: { 'Content-Type': 'application/json', 'X-FoodPath-Visit': '1' }, body: '{}' } : {}),
      signal: AbortSignal.timeout(4000),
    });
    if (!response.ok) return null;
    const data = await response.json();
    return Number.isSafeInteger(data.count) && data.count >= 0 ? data.count : null;
  } catch { return null; }
}
export function initVisits(doc = document) {
  const node = doc.getElementById('site-visits'); if (!node) return;
  const start = () => {
    if (doc.visibilityState === 'hidden') return;
    doc.removeEventListener('visibilitychange', start);
    setTimeout(async () => {
      if (doc.visibilityState === 'hidden') { doc.addEventListener('visibilitychange', start); return; }
      let count = null;
      try { count = await visitCount(); } catch { /* Storage may be unavailable. */ }
      if (count !== null) { node.textContent = `${count.toLocaleString()} ${doc.documentElement.lang === 'bn' ? 'সাইট ভিজিট' : 'site visits'}`; node.title = 'Approximate counted browser-tab sessions, not unique people'; node.hidden = false; }
    }, 1500);
  };
  if (doc.visibilityState === 'hidden') doc.addEventListener('visibilitychange', start); else start();
}
