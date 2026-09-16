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
  return pandals.filter(p => p.enabled && Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180 && p.coordinate_source)
    .map(p => ({ id: `pandal-${p.pandal_id}`, kind: 'pandal', label: p.name, lat: p.latitude, lng: p.longitude, count: 0 }));
}
let areas = []; let pandals = []; let frame = null; let key = ''; let chooseArea = () => {}; let started = false;
const send = () => { if (frame) frame.contentWindow.postMessage({ type: 'foodpath-map-data', key, language, markers: [...areas, ...pandals] }, location.origin); };
export function setMapPandals(value) { pandals = pandalMarkers(value); send(); }
export function renderAreaSummary(rows, activate) {
  areas = areaMarkers(rows); chooseArea = activate;
  const container = document.getElementById('chart-map'); container.replaceChildren();
  const mapped = mappedRows(rows).length;
  document.getElementById('map-coverage').textContent = language === 'bn'
    ? `${rows.length}টি নথির মধ্যে ${mapped}টির ভৌগোলিক তথ্য দেখানো হয়েছে; ${rows.length - mapped}টি বাদ।`
    : `Geographic coverage: ${mapped} of ${rows.length} records; ${rows.length - mapped} omitted for insufficient precision.`;
  for (const marker of areas) {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'map-key';
    button.textContent = `${marker.label} · ${marker.count}`;
    button.addEventListener('click', () => activate('areas', marker.label)); container.append(button);
  }
  if (!areas.length) container.textContent = language === 'bn' ? 'মানচিত্রে দেখানোর মতো যাচাই করা অবস্থান নেই।' : 'No reviewed locations available to plot.';
  send();
}
export async function initMapHost() {
  const button = document.getElementById('load-google-map');
  const status = document.getElementById('google-map-status');
  const fail = () => { status.textContent = text('Google map could not load. The area list is still available.'); document.getElementById('map-fallback').hidden = false; if (frame) frame.hidden = true; };
  try {
    const response = await fetch('maps-config.json', { credentials: 'omit', cache: 'no-store' });
    if (!response.ok) throw Error('No config');
    const config = await response.json();
    if (!/^AIza[A-Za-z0-9_-]{35}$/.test(config.browser_key || '')) throw Error('No key');
    key = config.browser_key; button.disabled = false;
    status.textContent = text('Map loads only on request. Google receives network information when you choose to load it.');
  } catch { status.textContent = text('Google map is not configured. Use the reported-area list below.'); }
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
  button.addEventListener('click', () => {
    if (started || !key) return; started = true; button.disabled = true;
    status.textContent = text('Loading the map…');
    frame = document.createElement('iframe'); frame.title = language === 'bn' ? 'Google মানচিত্রে এলাকা ও মণ্ডপ' : 'Reported areas and pandals on Google Maps';
    frame.src = `google-map.html?lang=${language}`; frame.className = 'google-map-frame'; frame.referrerPolicy = 'origin';
    document.getElementById('google-map-host').append(frame); timer = setTimeout(fail, 20000);
  });
}
