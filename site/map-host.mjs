import { mappedRows } from './geography.mjs';
import { language } from './locale.mjs';
import { text } from './foodpath-copy.mjs';

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
  return pandals.filter(p => p.enabled !== false && Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180 && p.coordinate_source)
    .map(p => ({ id: `pandal-${p.pandal_id}`, kind: 'pandal', label: p.name, lat: p.latitude, lng: p.longitude, count: 0 }));
}
let areas = []; let pandals = []; let frame = null; let key = ''; let chooseArea = () => {}; let started = false; let initialized = false; let selectedPandal = null;
const selectedMarker = () => pandals.find(p => p.id === `pandal-${selectedPandal}`);
const send = () => { if (frame) frame.contentWindow.postMessage({ type: 'foodpath-map-data', key, language, markers: [...areas, ...pandals], selectedPandalId: selectedMarker()?.id || null }, location.origin); };
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
    ? `${pandals.length}টি মণ্ডপের অবস্থান স্বতন্ত্র উৎসে যাচাই করা। আরও উৎসসমর্থিত মণ্ডপ খুঁজতে সার্চ ব্যবহার করুন।`
    : `${pandals.length} independently located pandals on the map. More source-backed listings are available through search.`;
  else node.textContent = language === 'bn'
    ? `${totalRows}টি নথির মধ্যে ${mapped}টির ভৌগোলিক তথ্য দেখানো হয়েছে; ${totalRows - mapped}টি বাদ।`
    : `Geographic coverage: ${mapped} of ${totalRows} records; ${totalRows - mapped} omitted for insufficient precision.`;
}
export function setMapPandals(value) { pandals = pandalMarkers(value); coverage(); send(); }
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
  const button = document.getElementById('load-google-map');
  const status = document.getElementById('google-map-status');
  let failed = false;
  const fail = () => { if (failed) return; failed = true; status.textContent = text('Google map could not load. The area list is still available.'); document.getElementById('map-fallback').hidden = false; if (frame) { frame.remove(); frame = null; } };
  try {
    key = await browserMapKey();
    if (!key) throw Error('No key');
    button.hidden = false; button.disabled = false;
    status.textContent = text('Map loads only on request. Google receives network information when you choose to load it.');
  } catch { button.hidden = true; status.textContent = text('Live map is temporarily unavailable. Use the festival and reported-area lists below.'); }
  let timer;
  window.addEventListener('message', event => {
    if (!frame || event.source !== frame.contentWindow || event.origin !== location.origin) return;
    if (event.data?.type === 'foodpath-map-ready') send();
    if (event.data?.type === 'foodpath-map-loaded') { clearTimeout(timer); document.getElementById('map-fallback').hidden = true; }
    if (event.data?.type === 'foodpath-map-error') { clearTimeout(timer); fail(); }
    if (event.data?.type === 'foodpath-map-select') {
      const selected = areas.find(m => m.id === event.data.id);
      if (selected) chooseArea('areas', selected.label);
      const pandal = pandals.find(m => m.id === event.data.id);
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
