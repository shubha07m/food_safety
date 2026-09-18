import { safeExternal } from './data.mjs';
import { language } from './locale.mjs';
import { text } from './foodpath-copy.mjs';
import { combineFood, publicFood, foodGeography, pandalFoodURL, INITIAL_FOOD_LIMIT } from './nearby-food.mjs';

export const FEATURED_IDS = ['bagbazar-sarbojanin'];
const validID = value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,255}$/.test(value);
export const normalize = value => String(value || '').normalize('NFC').toLocaleLowerCase().trim().replace(/\s+/g, ' ');
export function mapsURL(id) {
  if (!validID(id)) return null;
  return `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query: 'restaurant', query_place_id: id })}`;
}
export function parsePlaces(data, catalog = null) {
  if (data.schema_version !== 'places-1' || data.association_semantics !== 'historical_discovery_not_current_proximity'
    || !['pandals', 'restaurants', 'associations'].every(key => Array.isArray(data[key]))) throw Error('Invalid Places data');
  const rawPandals = catalog?.records || data.pandals;
  const pandals = rawPandals.filter(p => (p.enabled !== false) && validID(p.pandal_id) && typeof p.name === 'string' && typeof p.area === 'string');
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
  const discoveries = new Map();
  const discoveryFields = new Set([
    'pandal_id', 'observed_at', 'expires_at', 'candidates_returned',
    'result_limit_reached', 'primary_result_count', 'supplemental_search_count',
    'raw_candidate_count', 'candidate_unique_count', 'association_count',
    'saturation_encountered', 'overlap_ratio', 'calls_used', 'last_enriched_at',
  ]);
  for (const d of data.discoveries || []) {
    if (!ids.has(d.pandal_id) || discoveries.has(d.pandal_id)
      || Object.keys(d).some(k => !discoveryFields.has(k))) throw Error('Invalid discovery metadata');
    discoveries.set(d.pandal_id, d);
  }
  return { pandals, groups, discoveries, index: pandals.map(p => ({ p, query: normalize(`${p.name} ${p.name_bn || ''} ${(p.aliases || []).join(' ')} ${p.area} ${p.neighborhood || ''} ${p.city || ''}`) })) };
}
export function discoveryState(pandal, discovery, rows, now = Date.now()) {
  if (!Number.isFinite(pandal.latitude) || !Number.isFinite(pandal.longitude)) return 'unavailable';
  if (!discovery) return rows.length ? 'stale' : 'not_run';
  if (!Number.isFinite(Date.parse(discovery.expires_at)) || Date.parse(discovery.expires_at) <= now) return 'stale';
  return rows.length ? 'current_nonzero' : 'current_zero';
}
export function searchPandals(index, query, limit = 8) {
  const tokens = normalize(query).split(' ').filter(Boolean);
  return index.filter(row => tokens.every(token => row.query.includes(token))).slice(0, Math.min(8, limit)).map(row => row.p);
}
export function featuredPandals(pandals, ids = null) {
  ids = ids || [...pandals.filter(p => p.featured).map(p => p.pandal_id), ...FEATURED_IDS];
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
function renderFood(selected, data, pandal) {
  const info = publicFood(data, pandal);
  const rows = info.rows;
  selected.append(el('h4', text('Nearby food')));
  if (rows.length) {
    const count = el('p', `${info.named_public_count} ${text('named places from the current OpenStreetMap snapshot')}`);
    count.id = 'nearby-food-count'; selected.append(count);
    if (info.named_snapshot_count > rows.length) selected.append(el('p', text('Showing the nearest 20 named places; this is not a quality ranking.'), 'fine-print'));
  } else {
    selected.append(el('p', text('Named nearby food listings are not yet available from the current independent data snapshot.'), 'notice'));
    const url = pandalFoodURL(pandal);
    if (url) {
      const link = el('a', text('Explore restaurants around this pandal on Google Maps ↗'), 'button secondary');
      link.href = url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.dataset.foodSearch = '';
      selected.append(link);
    } else selected.append(el('p', text('Restaurant discovery is not yet available for this pandal.'), 'fine-print'));
  }
  const list = el('ol', null, 'restaurant-links'); selected.append(list);
  let shown = 0;
  const more = el('button', text('Show more nearby food'), 'button secondary'); more.type = 'button'; more.dataset.foodMore = '';
  const append = () => {
    for (const row of rows.slice(shown, shown + INITIAL_FOOD_LIMIT)) {
      const li = el('li'); const copy = el('div');
      copy.append(el('strong', (language === 'bn' && row.name_bn?.trim()) || row.name));
      const category = { restaurant: 'Restaurant', cafe: 'Cafe', fast_food: 'Fast food', ice_cream: 'Ice cream', food_court: 'Food court', bakery: 'Bakery', confectionery: 'Confectionery' }[row.category];
      copy.append(el('small', [text(category || row.category), row.cuisine?.replaceAll(';', ', ')].filter(Boolean).join(' · ')));
      copy.append(el('small', `${Math.round(row.distance)} m · ${text('Approximate straight-line distance')}`));
      const link = el('a', text('Open in Google Maps ↗'), 'button secondary');
      link.href = row.url; link.target = '_blank'; link.rel = 'noopener noreferrer'; link.setAttribute('aria-label', `${link.textContent} — ${row.name}`);
      li.append(copy, link); list.append(li);
    }
    shown = Math.min(shown + INITIAL_FOOD_LIMIT, rows.length); more.hidden = shown >= rows.length;
  };
  more.addEventListener('click', append); selected.append(more); append();
  const footer = el('p', text('Food-place data') + ': ', 'fine-print food-provenance');
  const credit = el('a', '© OpenStreetMap contributors'); credit.href = 'https://www.openstreetmap.org/copyright'; credit.rel = 'noopener noreferrer';
  footer.append(credit, document.createTextNode(` · ${text('Nearby is not a recommendation, inspection, or safety rating.')}`));
  selected.append(footer);
  if (rows[0]?.at) selected.append(el('small', `${text('Snapshot date')}: ${rows[0].at}`, 'fine-print'));
  return info;
}

export async function initPuja(onData = () => {}) {
  const input = document.getElementById('pandal-search');
  const options = document.getElementById('pandal-options');
  const status = document.getElementById('pandal-search-status');
  const selected = document.getElementById('selected-pandal');
  try {
    const [response, catalogResponse] = await Promise.all([
      fetch('data/places.json', { credentials: 'omit' }),
      fetch('data/pandals.json', { credentials: 'omit' }),
    ]);
    if (!response.ok || !catalogResponse.ok) throw Error('Unavailable');
    let data = parsePlaces(await response.json(), await catalogResponse.json());
    // Missing optional provider files preserve the existing Google-only contract.
    const optional = async path => { try { const r = await fetch(path, { credentials: 'omit' }); return r.ok ? await r.json() : null; } catch { return null; } };
    const policy = await optional('data/food_provider.json');
    const osm = policy && policy.provider !== 'google' ? await optional('data/osm_food.json') : null;
    data = combineFood(data, osm, policy);
    let matches = []; let active = -1;
    const close = () => { options.hidden = true; input.setAttribute('aria-expanded', 'false'); input.removeAttribute('aria-activedescendant'); active = -1; };
    const select = (p, updateURL = true) => {
      close(); input.value = language === 'bn' && p.name_bn ? p.name_bn : p.name;
      selected.hidden = false; selected.replaceChildren();
      selected.append(el('p', text('Selected pandal'), 'eyebrow'));
      const heading = el('h3', input.value); heading.id = 'selected-pandal-title'; heading.tabIndex = -1;
      selected.append(heading, el('p', `${p.name_bn && language !== 'bn' ? `${p.name_bn} · ` : ''}${p.neighborhood || p.area} · ${p.city || ''}`, 'pandal-area'));
      if (p.location_precision === 'source_zone') selected.append(el('p', text('Location is the directory’s broad zone, not a verified street address.')));
      if (p.year) selected.append(el('p', `${text('Source listing year')}: ${p.year}. ${text('This does not confirm this year’s venue or opening times.')}`, 'fine-print'));
      if (p.subtitle) selected.append(el('p', p.subtitle, 'pandal-subtitle'));
      const mapReady = Number.isFinite(p.latitude) && Number.isFinite(p.longitude);
      if (!mapReady) selected.append(el('p', text('Map location is not yet independently verified.'), 'notice'));
      else if (p.coordinate_precision === 'street' || p.coordinate_precision === 'neighborhood') selected.append(el('p', text('Map location is an independently sourced approximate anchor.'), 'notice'));
      else selected.append(el('p', text('Map location is independently sourced.'), 'notice'));
      document.dispatchEvent(new CustomEvent('foodpath-focus-pandal', { detail: p.pandal_id }));
      const provenance = el('details'); provenance.append(el('summary', text('Read source provenance')));
      for (const source of p.sources || []) {
        const paragraph = el('p'); const href = safeExternal(source.source_url);
        if (href) { const link = el('a', source.source_title || source.publisher); link.href = href; link.target = '_blank'; link.rel = 'noopener noreferrer'; paragraph.append(link); }
        else paragraph.append(el('span', source.source_title || source.publisher));
        paragraph.append(document.createTextNode(` — “${source.quote}”`)); provenance.append(paragraph);
      }
      selected.append(provenance);
      const food = renderFood(selected, data, p);
      document.querySelectorAll('[data-food-pandal]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.foodPandal === p.pandal_id)));
      if (updateURL) { const url = new URL(location.href); url.searchParams.set('pandal', p.pandal_id); url.hash = 'puja'; history.replaceState(null, '', url); }
      status.textContent = `${input.value} · ${food.named_public_count ? `${food.named_public_count} ${text('named nearby food places')}` : text('Named listings pending')}`;
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
    const geography = document.getElementById('festival-food-entries');
    for (const { pandal, count } of foodGeography(data)) {
      const button = el('button', null, 'food-geography-chip'); button.type = 'button'; button.dataset.foodPandal = pandal.pandal_id; button.setAttribute('aria-pressed', 'false');
      button.append(el('strong', language === 'bn' && pandal.name_bn ? pandal.name_bn : pandal.name),
        el('span', count ? `${count} ${text('named nearby food places')}` : text('Named listings pending')));
      button.addEventListener('click', () => document.dispatchEvent(new CustomEvent('foodpath-select-pandal', { detail: pandal.pandal_id })));
      geography?.append(button);
    }
    const featured = document.getElementById('featured-pandals');
    for (const p of featuredPandals(data.pandals)) {
      const card = el('article', null, 'pandal-card'); card.append(el('p', `${p.area} · ${p.city || 'West Bengal'}`, 'eyebrow'), el('h4', language === 'bn' && p.name_bn ? p.name_bn : p.name));
      if (p.subtitle) card.append(el('p', p.subtitle));
      const button = el('button', text('View restaurant links'), 'button secondary'); button.type = 'button'; button.addEventListener('click', () => { select(p); selected.scrollIntoView({ block: 'nearest' }); document.getElementById('selected-pandal-title').focus({ preventScroll: true }); }); card.append(button); featured.append(card);
    }
    status.textContent = language === 'bn' ? `${data.pandals.length}টি উৎসসমর্থিত মণ্ডপ। নাম বা এলাকা লিখে খুঁজুন।` : `${data.pandals.length} source-backed pandals. Search by name or area; this is not a complete directory.`;
    const fromURL = () => { const p = data.pandals.find(p => p.pandal_id === new URLSearchParams(location.search).get('pandal')); if (p) select(p, false); };
    fromURL(); window.addEventListener('popstate', fromURL);
    document.addEventListener('foodpath-select-pandal', event => {
      const p = data.pandals.find(p => p.pandal_id === event.detail);
      if (p) { select(p); selected.scrollIntoView({ block: 'start' }); document.getElementById('selected-pandal-title').focus({ preventScroll: true }); }
    });
    onData(data.pandals);
  } catch { input.disabled = true; status.textContent = text('Pandal data is unavailable. Please try again later.'); }
}
