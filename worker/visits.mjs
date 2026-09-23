// Aggregate-only, approximate tab-session counts. No request metadata is persisted.
const headers = { 'Content-Type': 'application/json', 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff' };
const reply = (status, body) => new Response(JSON.stringify(body), { status, headers });
export function allowed(request) {
  const url = new URL(request.url);
  if (url.pathname !== '/api/visits' || url.search) return false;
  if (request.method === 'GET') return true;
  return request.method === 'POST' && request.headers.get('Origin') === url.origin
    && request.headers.get('Sec-Fetch-Site') === 'same-origin'
    && request.headers.get('Content-Type') === 'application/json'
    && request.headers.get('X-FoodPath-Visit') === '1';
}
export default {
  async fetch(request, env) {
    if (new URL(request.url).pathname !== '/api/visits') return env.ASSETS.fetch(request);
    if (!allowed(request)) return reply(400, { unavailable: true });
    if (request.method === 'POST') {
      // Empty JSON only. Do not read/log/store arbitrary client bodies or metadata.
      if (request.headers.get('Content-Length') !== '2') return reply(400, { unavailable: true });
      const reader = request.body?.getReader();
      if (!reader) return reply(400, { unavailable: true });
      let body = ''; let bytes = 0;
      try {
        while (bytes < 3) {
          const chunk = await reader.read();
          if (chunk.done) break;
          bytes += chunk.value.byteLength;
          if (bytes > 2) break;
          body += new TextDecoder().decode(chunk.value);
        }
      } catch { return reply(400, { unavailable: true }); }
      finally { await reader.cancel().catch(() => {}); }
      if (bytes !== 2 || body !== '{}') return reply(400, { unavailable: true });
    }
    try {
      const id = env.VISITS.idFromName('aggregate-v1');
      // Reconstruct a minimal internal request; no edge/client headers are forwarded.
      return await env.VISITS.get(id).fetch(new Request('https://counter.internal/', { method: request.method }));
    } catch { return reply(503, { unavailable: true }); }
  },
};
export class VisitCounter {
  constructor(ctx) { this.storage = ctx.storage; }
  async fetch(request) {
    if (!['GET', 'POST'].includes(request.method)) return reply(405, { unavailable: true });
    try {
      const result = await this.storage.transaction(async tx => {
        const state = await tx.get('aggregate') || { count: 0 };
        if (request.method === 'GET') return { count: state.count };
        const now = new Date(); const day = now.toISOString().slice(0, 10); const minute = Math.floor(now.getTime() / 60000);
        const daily = state.day === day ? state.daily : 0; const recent = state.minute === minute ? state.recent : 0;
        // Bounds storage writes, not incoming requests or unique-human accuracy.
        if (daily >= 10000 || recent >= 60) return { count: state.count, limited: true };
        await tx.put('aggregate', { count: state.count + 1, day, daily: daily + 1, minute, recent: recent + 1 });
        return { count: state.count + 1 };
      });
      return reply(200, result);
    } catch { return reply(503, { unavailable: true }); }
  }
}
