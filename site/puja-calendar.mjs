// Date-only discovery. Never changes edition, venue or geographic eligibility.
import { safeExternal } from './data.mjs';

const zone = 'America/Los_Angeles';
export function californiaToday(now = new Date()) {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(now);
  const get = type => parts.find(p => p.type === type).value;
  return `${get('year')}-${get('month')}-${get('day')}`;
}
function validDate(value) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const date = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(date.valueOf()) && date.toISOString().slice(0, 10) === value;
}
export function calendarGroups(pandals, today = californiaToday()) {
  const seen = new Set(); const groups = new Map();
  for (const p of pandals) {
    if (p.region_id !== 'california' || p.enabled === false || !p.pandal_id || seen.has(p.pandal_id)) continue;
    const d = p.reviewed_dates || (p.edition?.confirmed ? p.edition : null);
    const end = d?.end_date || d?.start_date;
    if (!d?.reviewed_at || d.timezone !== zone || !validDate(d.start_date) || !validDate(end)
      || end < d.start_date || end < today) continue;
    const sources = new Set((p.sources || []).map(s => s.source_url));
    const evidence = (d.evidence || []).find(e => (e.evidence_kind || 'source_quote') === 'source_quote'
      && e.quote?.trim() && safeExternal(e.source_url) && sources.has(e.source_url));
    if (!evidence) continue; // Neither legacy event_dates nor owner identity approval is date evidence.
    seen.add(p.pandal_id);
    const key = `${d.start_date}/${end}`;
    if (!groups.has(key)) groups.set(key, { start: d.start_date, end, ongoing: d.start_date <= today, entries: [] });
    groups.get(key).entries.push({ pandal: p, source: evidence.source_url });
  }
  return [...groups.values()].sort((a, b) => a.start.localeCompare(b.start) || a.end.localeCompare(b.end));
}
export function calendarRange(start, end, bn = false) {
  const fmt = new Intl.DateTimeFormat(bn ? 'bn-BD' : 'en-US', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' });
  const a = new Date(`${start}T12:00:00Z`); const b = new Date(`${end}T12:00:00Z`);
  return start === end ? fmt.format(a) : fmt.formatRange(a, b);
}
export function renderCalendar(host, pandals, region, select, { bn = false, today = californiaToday(), doc = document } = {}) {
  host.replaceChildren(); host.hidden = region !== 'california';
  if (host.hidden) return;
  const t = (en, bengali) => bn ? bengali : en;
  const el = (tag, text, cls) => { const n = doc.createElement(tag); if (text) n.textContent = text; if (cls) n.className = cls; return n; };
  const heading = el('h3', t('California Puja Calendar', 'ক্যালিফোর্নিয়ার পুজোর দিনপঞ্জি'));
  heading.id = 'puja-calendar-title';
  host.append(heading, el('p', t('Reviewed dates from our listings — not a complete regional calendar.', 'আমাদের তালিকার পর্যালোচিত তারিখ — অঞ্চলের সম্পূর্ণ দিনপঞ্জি নয়।'), 'fine-print'));
  const groups = calendarGroups(pandals, today);
  if (!groups.length) { host.append(el('p', t('Reviewed upcoming dates are not available yet.', 'আসন্ন পুজোর পর্যালোচিত তারিখ এখনও পাওয়া যায়নি।'), 'calendar-empty')); return; }
  const list = el('ul', null, 'calendar-ranges');
  for (const g of groups) {
    const row = el('li', null, 'calendar-range'); const date = el('div', null, 'calendar-date');
    date.append(el('strong', calendarRange(g.start, g.end, bn)));
    const n = g.entries.length.toLocaleString(bn ? 'bn-BD' : 'en-US');
    const count = bn ? `${n}টি পুজো` : `${n} ${g.entries.length === 1 ? 'Puja' : 'Pujas'}`;
    date.append(el('span', `${count} · ${g.ongoing ? t('Ongoing', 'চলছে') : t('Upcoming', 'আসন্ন')}`, 'fine-print'));
    const entries = el('ul', null, 'calendar-pujas');
    for (const { pandal: p, source } of g.entries) {
      const item = el('li'); const name = bn && p.name_bn ? p.name_bn : p.name;
      const button = el('button', name, 'calendar-select'); button.type = 'button';
      button.addEventListener('click', () => select(p.pandal_id));
      const link = el('a', t('Source ↗', 'উৎস ↗'), 'calendar-source'); link.href = source;
      link.target = '_blank'; link.rel = 'noopener noreferrer';
      link.setAttribute('aria-label', t(`Date source for ${name}`, `${name}-এর তারিখের উৎস`));
      item.append(button, link); entries.append(item);
    }
    row.append(date, entries); list.append(row);
  }
  host.append(list);
}
