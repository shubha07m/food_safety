import { safeExternal } from './data.mjs';
import { language } from './locale.mjs';
import { text } from './foodpath-copy.mjs';

export const FEATURED_IDS = ['bagbazar-sarbojanin'];
const validID = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,255}$/.test(value);
export const normalize = value => String(value || '').normalize('NFC').toLocaleLowerCase().trim().replace(/\s+/g, ' ');
export function mapsURL(id) {
  if (!validID(id)) return null;
  return `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query: 'restaurant', query_place_id: id })}`;
}
export function parsePlaces(data) {
  if (data.schema_version !== 'places-1' || data.association_semantics !== 'historical_discovery_not_current_proximity'
    || !['pandals', 'restaurants', 'associations'].every(key => Array.isArray(data[key]))) throw Error('Invalid Places data');
  const pandals = data.pandals.filter(p => p.enabled && validID(p.pandal_id) && typeof p.name === 'string' && typeof p.area === 'string');
  const restaurants = new Map();
  for (const r of data.restaurants) {
    if (!validID(r.place_id) || Object.keys(r).some(k => !['place_id', 'source', 'curated', 'google_maps_url'].includes(k))) throw Error('Restricted restaurant fields');
    const source = r.curated && safeExternal(r.curated.independent_source);
    const independent = source && !/google|goo\.gl|gstatic/i.test(new URL(source).hostname) && r.curated.source_kind === 'independently_curated';
    restaurants.set(r.place_id, { id: r.place_id, name: independent && typeof r.curated.name === 'string' ? r.curated.name : null, url: mapsURL(r.place_id) });
  }
  const groups = new Map(); const seen = new Set(); const ids = new Set(pandals.map(p => p.pandal_id));
  for (const a of data.associations) {
    if (Object.keys(a).some(k => !['pandal_id', 'place_id', 'observed_at', 'provenance'].includes(k))) throw Error('Restricted association fields');
    const key = `${a.pandal_id}/${a.place_id}`;
    if (ids.has(a.pandal_id) && restaurants.has(a.place_id) && !seen.has(key)) {
      const matches = groups.get(a.pandal_id) || [];
      matches.push({ ...restaurants.get(a.place_id), at: /^\d{4}-\d{2}-\d{2}T/.test(a.observed_at) ? a.observed_at.slice(0, 10) : null });
      groups.set(a.pandal_id, matches); seen.add(key);
    }
  }
  return { pandals, groups, index: pandals.map(p => ({ p, query: normalize(`${p.name} ${p.name_bn || ''} ${p.area}`) })) };
}
export function searchPandals(index, query, limit = 8) {
  const tokens = normalize(query).split(' ').filter(Boolean);
  return index.filter(row => tokens.every(token => row.query.includes(token))).slice(0, Math.min(8, limit)).map(row => row.p);
}
export function featuredPandals(pandals, ids = FEATURED_IDS) {
  return [...new Set(ids)].map(id => pandals.find(p => p.pandal_id === id)).filter(Boolean).slice(0, 6);
}
export function nextOption(key, active, count) {
  if (!count || key === 'Escape') return -1;
  if (key === 'ArrowDown') return (active + 1) % count;
  if (key === 'ArrowUp') return active <= 0 ? count - 1 : active - 1;
  return active;
}
function el(tag, value, className) {
  const item = document.createElement(tag);
  if (value != null) item.textContent = value;
  if (className) item.className = className;
  return item;
}
export async function initPuja(onData = () => {}) {
  const input = document.getElementById('pandal-search');
  const options = document.getElementById('pandal-options');
  const status = document.getElementById('pandal-search-status');
  const selected = document.getElementById('selected-pandal');
  try {
    const response = await fetch('data/places.json', { credentials: 'omit' });
    if (!response.ok) throw Error('Unavailable');
    const data = parsePlaces(await response.json());
    let matches = []; let active = -1;
    const close = () => { options.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); active = -1; };
    const select = (p, updateURL = true) => {
      close(); input.value = language === 'bn' && p.name_bn ? p.name_bn : p.name;
      selected.hidden = false; selected.replaceChildren();
      selected.append(el('p', text('Selected pandal'), 'eyebrow'));
      const heading = el('h3', input.value); heading.id = 'selected-pandal-title'; heading.tabIndex = -1;
      selected.append(heading, el('p', `${p.name_bn && language !== 'bn' ? `${p.name_bn} · ` : ''}${p.area}`, 'pandal-area'));
      const provenance = el('details'); provenance.append(el('summary', text('Read coordinate provenance')), el('p', p.notes || p.area)); selected.append(provenance);
      const rows = data.groups.get(p.pandal_id) || [];
      selected.append(el('h4', `${text('Recorded restaurant links')} · ${rows.length}`), el('p', text('Historical discovery matches, not a current proximity guarantee. Current distances are unavailable.'), 'notice'));
      const attribution = el('p', 'Google Maps', 'google-attribution'); attribution.translate = false; selected.append(attribution);
      if (!rows.length) selected.append(el('p', text('No restaurant links published yet. This does not mean there are no restaurants nearby.')));
      const list = el('ol', null, 'restaurant-links'); selected.append(list);
      let shown = 0;
      const more = el('button', text('Show more restaurant links'), 'button secondary'); more.type = 'button';
      const append = () => {
        rows.slice(shown, shown + 20).forEach((row, i) => {
          const li = el('li'); const copy = el('div'); copy.append(el('strong', row.name || text('Restaurant on Google Maps')));
          if (row.at) copy.append(el('small', `${text('Discovery date')}: ${row.at}`));
          const a = el('a', text('Open in Google Maps ↗'), 'button secondary'); a.href = row.url; a.target = '_blank'; a.rel = 'noopener noreferrer'; a.setAttribute('aria-label', `${a.textContent} — ${row.name || shown + i + 1}`);
          li.append(copy, a); list.append(li);
        });
        shown += 20; more.hidden = shown >= rows.length;
      };
      more.addEventListener('click', append); selected.append(more); append();
      if (updateURL) { const url = new URL(location.href); url.searchParams.set('pandal', p.pandal_id); url.hash = 'puja'; history.replaceState(null, '', url); }
      status.textContent = `${input.value} · ${rows.length} ${text('Recorded restaurant links')}`;
    };
    const update = () => {
      matches = searchPandals(data.index, input.value); active = -1; options.replaceChildren();
      matches.forEach((p, i) => {
        const option = el('li'); option.id = `pandal-option-${i}`; option.setAttribute('role', 'option'); option.setAttribute('aria-selected', 'false');
        option.append(el('strong', p.name), el('span', `${p.name_bn || ''} · ${p.area}`));
        option.addEventListener('pointerdown', e => e.preventDefault()); option.addEventListener('click', () => select(p)); options.append(option);
      });
      options.hidden = !matches.length; input.setAttribute('aria-expanded', String(!!matches.length)); input.removeAttribute('aria-activedescendant');
      status.textContent = matches.length ? (language === 'bn' ? `${matches.length}টি ফল দেখানো হচ্ছে। তিরচিহ্ন ও Enter ব্যবহার করুন।` : `${matches.length} matches shown. Use arrow keys and Enter to select.`) : text('No matching pandals. Try another name or area.');
    };
    input.addEventListener('input', update);
    input.addEventListener('keydown', e => {
      if (e.key === 'Escape') { close(); return; }
      if (['ArrowDown', 'ArrowUp'].includes(e.key)) {
        e.preventDefault(); if (options.hidden) update(); active = nextOption(e.key, active, matches.length);
        [...options.children].forEach((li, i) => li.setAttribute('aria-selected', String(i === active)));
        if (active >= 0) { input.setAttribute('aria-activedescendant', options.children[active].id); options.children[active].scrollIntoView({ block: 'nearest' }); }
      }
      if (e.key === 'Enter' && !options.hidden && matches.length) { e.preventDefault(); select(matches[Math.max(0, active)]); }
    });
    input.addEventListener('blur', close);
    const featured = document.getElementById('featured-pandals');
    for (const p of featuredPandals(data.pandals)) {
      const card = el('article', null, 'pandal-card'); card.append(el('p', p.area, 'eyebrow'), el('h4', language === 'bn' && p.name_bn ? p.name_bn : p.name));
      const button = el('button', text('View restaurant links'), 'button secondary'); button.type = 'button'; button.addEventListener('click', () => { select(p); selected.scrollIntoView({ block: 'nearest' }); document.getElementById('selected-pandal-title').focus({ preventScroll: true }); }); card.append(button); featured.append(card);
    }
    status.textContent = text('Type a name or area to search the current collection.');
    const fromURL = () => { const p = data.pandals.find(p => p.pandal_id === new URLSearchParams(location.search).get('pandal')); if (p) select(p, false); };
    fromURL(); window.addEventListener('popstate', fromURL);
    document.addEventListener('foodpath-select-pandal', event => {
      const p = data.pandals.find(p => p.pandal_id === event.detail);
      if (p) { select(p); selected.scrollIntoView({ block: 'start' }); document.getElementById('selected-pandal-title').focus({ preventScroll: true }); }
    });
    onData(data.pandals);
  } catch { input.disabled = true; status.textContent = text('Pandal data is unavailable. Please try again later.'); }
}
