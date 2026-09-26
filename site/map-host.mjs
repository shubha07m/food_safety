import { mappedRows } from './geography.mjs';
import { language } from './locale.mjs';
import { text } from './foodpath-copy.mjs';
import { effectiveLocation } from './puja-location.mjs';

export function areaMarkers(rows) {
  const groups = new Map();
  for (const row of mappedRows(rows)) {
    const c = row.derived_context; const area = c.normalized_area || row.reported_fact.area;
    const key = `${area}/${c.latitude}/${c.longitude}`;
    const marker = groups.get(key) || { id: `area-${groups.size}`, kind: 'area', label: area, lat: c.latitude, lng: c.longitude, count: 0 };
    marker.count += 1; groups.set(key, marker);
  }
  return [...groups.values()];
}
export function pandalMarkers(pandals) {
  return pandals.map(p => ({ p, loc: effectiveLocation(p) })).filter(({ loc }) => loc.map_eligible)
    .map(({ p, loc }) => ({ id: `pandal-${p.pandal_id}`, kind: 'pandal', label: p.name, lat: loc.latitude, lng: loc.longitude, precision: loc.coordinate_precision || 'neighborhood', count: 0 }));
}
let areas = []; let pandals = []; let frame = null; let key = ''; let chooseArea = () => {}; let started = false; let initialized = false; let selectedPandal = null;
let regionConfig = null;
let globalPandals = []; let scope = 'region';
export function scopeMarkers(regional, global, areas, scope, safety) {
  return scope === 'world' ? global : safety ? [...areas, ...regional] : regional;
}
const activePandals = () => scope === 'world' ? globalPandals : pandals;
const selectedMarker = () => activePandals().find(p => p.id === `pandal-${selectedPandal}`);
const send = () => { if (frame) frame.contentWindow.postMessage({ type: 'foodpath-map-data', key, language,
  regionId: scope === 'world' ? 'world' : regionConfig?.region_id, mapCenter: scope === 'world' ? {lat: 20, lng: 0} : regionConfig?.default_map_center, mapZoom: scope === 'world' ? 2 : regionConfig?.default_map_zoom,
  safetyContext: scope !== 'world' && regionConfig?.safety_context !== false,
  markers: scopeMarkers(pandals, globalPandals, areas, scope, regionConfig?.safety_context !== false), selectedPandalId: selectedMarker()?.id || null }, location.origin); };
let mapped = 0; let totalRows = 0;
export async function browserMapKey(fetcher = fetch) {
  const response = await fetcher('maps-config.json', { credentials: 'omit', cache: 'no-store' });
  if (!response.ok) return '';
  const config = await response.json();
  return /^AIza[A-Za-z0-9_-]{35}$/.test(config.browser_key || '') ? config.browser_key : '';
}
function coverage() {
  const node = document.getElementById('map-coverage');
  if (document.body.classList.contains('puja-route')) node.textContent = language === 'bn'
    ? `${activePandals().length}টি মণ্ডপের অবস্থান স্বতন্ত্র উৎসে যাচাই করা। আরও উৎসসমর্থিত মণ্ডপ খুঁজতে সার্চ ব্যবহার করুন।`
    : `${activePandals().length} independently located pandals on the map. More source-backed listings are available through search.`;
  else node.textContent = language === 'bn'
    ? `${totalRows}টি নথির মধ্যে ${mapped}টির ভৌগোলিক তথ্য দেখানো হয়েছে; ${totalRows - mapped}টি বাদ।`
    : `Geographic coverage: ${mapped} of ${totalRows} records; ${totalRows - mapped} omitted for insufficient precision.`;
}
export function setMapPandals(value, region = null, all = value) {
  if (regionConfig?.region_id !== region?.region_id) selectedPandal = null;
  regionConfig = region; pandals = pandalMarkers(value); globalPandals = pandalMarkers(all); coverage(); send();
  document.querySelectorAll('[data-safety-context]').forEach(n => { n.hidden = scope === 'world' || region?.safety_context === false; });
}
export function renderAreaSummary(rows, activate) {
  areas = areaMarkers(rows); chooseArea = activate;
  const container = document.getElementById('chart-map'); container.replaceChildren();
  mapped = mappedRows(rows).length; totalRows = rows.length; coverage();
  for (const marker of areas) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'map-key';
    button.textContent = `${marker.label} · ${marker.count}`;
    button.addEventListener('click', () => activate('areas', marker.label)); container.append(button);
  }
  if (!areas.length) container.textContent = language === 'bn' ? 'মানচিত্রে দেখানোর মতো যাচাই করা অবস্থান নেই।' : 'No reviewed locations available to plot.';
  send();
}
export async function initMapHost() {
  if (initialized) return;
  initialized = true;
  const scopes = document.createElement('div'); scopes.className = 'map-scopes puja-only'; scopes.setAttribute('role', 'group'); scopes.setAttribute('aria-label', 'Map scope');
  scopes.hidden = !document.body.classList.contains('puja-route');
  for (const [id, label] of [['region', language === 'bn' ? 'নির্বাচিত অঞ্চল' : 'Selected region'], ['world', language === 'bn' ? 'বিশ্বের পুজোর মানচিত্র' : 'World Puja map']]) {
    const action = document.createElement('button'); action.type = 'button'; action.className = 'button secondary'; action.textContent = label; action.dataset.mapScope = id; action.setAttribute('aria-pressed', String(scope === id));
    action.addEventListener('click', () => {
      scope = id; selectedPandal = null;
      scopes.querySelectorAll('button').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.mapScope === scope)));
      document.querySelectorAll('[data-safety-context]').forEach(n => { n.hidden = scope === 'world' || regionConfig?.safety_context === false; });
      coverage(); send();
    }); scopes.append(action);
  }
  document.getElementById('google-map-host').before(scopes);
  const button = document.getElementById('load-google-map');
  const status = document.getElementById('google-map-status');
  let failed = false;
  const fail = () => { if (failed) return; failed = true; status.textContent = text('Live map is temporarily unavailable. You can still browse the lists and search.'); document.getElementById('map-fallback').hidden = false; if (frame) { frame.remove(); frame = null; } };
  try {
    key = await browserMapKey();
    if (!key) throw Error('No key');
    button.hidden = false; button.disabled = false;
    status.textContent = text('Map loads only on request. Google receives network information when you choose to load it.');
  } catch { button.hidden = true; status.textContent = text('Live map is temporarily unavailable. You can still browse the lists and search.'); }
  let timer;
  window.addEventListener('message', event => {
    if (!frame || event.source !== frame.contentWindow || event.origin !== location.origin) return;
    if (event.data?.type === 'foodpath-map-ready') send();
    if (event.data?.type === 'foodpath-map-loaded') { clearTimeout(timer); document.getElementById('map-fallback').hidden = true; }
    if (event.data?.type === 'foodpath-map-error') { clearTimeout(timer); fail(); }
    if (event.data?.type === 'foodpath-map-select') {
      const selected = scope !== 'world' && areas.find(m => m.id === event.data.id);
      if (selected) chooseArea('areas', selected.label);
      const pandal = activePandals().find(m => m.id === event.data.id);
      if (pandal) document.dispatchEvent(new CustomEvent('foodpath-select-pandal', { detail: pandal.id.slice(7) }));
    }
  });
  document.addEventListener('foodpath-focus-pandal', event => {
    selectedPandal = event.detail;
    const marker = selectedMarker();
    if (frame) frame.contentWindow.postMessage({ type: 'foodpath-map-focus', id: marker?.id || null }, location.origin);
  });
  button.addEventListener('click', () => {
    if (started || !key) return; started = true; button.disabled = true;
    status.textContent = text('Loading the map…');
    frame = document.createElement('iframe'); frame.title = language === 'bn' ? 'Google মানচিত্রে এলাকা ও মণ্ডপ' : 'Reported areas and pandals on Google Maps';
    frame.src = `google-map.html?lang=${language}`; frame.className = 'google-map-frame'; frame.referrerPolicy = 'origin';
    document.getElementById('google-map-host').append(frame); timer = setTimeout(fail, 20000);
  });
}
