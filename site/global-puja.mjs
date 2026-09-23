// Geolocation is deliberately local, ephemeral and initiated only by a click.
export function mapped(p) {
  return Number.isFinite(p.latitude) && Math.abs(p.latitude) <= 90 && Number.isFinite(p.longitude)
    && Math.abs(p.longitude) <= 180 && !!p.coordinate_source;
}
export function distanceKm(a, b) {
  const rad = n => n * Math.PI / 180;
  const dlat = rad(b.latitude - a.latitude); const dlon = rad(b.longitude - a.longitude);
  const h = Math.sin(dlat / 2) ** 2 + Math.cos(rad(a.latitude)) * Math.cos(rad(b.latitude)) * Math.sin(dlon / 2) ** 2;
  return 6371.0088 * 2 * Math.asin(Math.min(1, Math.sqrt(h)));
}
export function nearestPujas(pandals, point, radiusKm = 100) {
  if (!Number.isFinite(point?.latitude) || Math.abs(point.latitude) > 90 || !Number.isFinite(point?.longitude) || Math.abs(point.longitude) > 180) return [];
  return pandals.filter(mapped).map(p => ({ pandal: p, distance: distanceKm(point, p) }))
    .filter(r => r.distance <= radiusKm).sort((a, b) => a.distance - b.distance || a.pandal.pandal_id.localeCompare(b.pandal.pandal_id)).slice(0, 5);
}
export function resolvePuja(pandals, regions, id, fallback = 'kolkata') {
  const pandal = pandals.find(p => p.pandal_id === id);
  const region = regions.find(r => r.region_id === (pandal?.region_id || fallback));
  return pandal && region ? { pandal, region } : null;
}
export function initNearMe(pandals, select, { doc = document, geo = navigator.geolocation, bn = false } = {}) {
  const button = doc.getElementById('puja-near-me'); const status = doc.getElementById('near-me-status'); const list = doc.getElementById('near-me-results');
  let pending = false;
  button.addEventListener('click', () => {
    if (pending) return;
    list.replaceChildren();
    if (!geo) { status.textContent = bn ? 'অবস্থান পাওয়া যাচ্ছে না। অঞ্চল বেছে খুঁজুন।' : 'Location is unavailable. Choose a region to browse instead.'; return; }
    pending = true; button.disabled = true;
    status.textContent = bn ? 'শুধু এই অনুরোধের জন্য অবস্থানের অনুমতি দিন।' : 'Allow location for this request. It stays in this page only.';
    const finish = () => { pending = false; button.disabled = false; };
    try { geo.getCurrentPosition(position => {
      const rows = nearestPujas(pandals, position.coords);
      finish();
      status.textContent = rows.length ? (bn ? 'আনুমানিক সরলরেখার দূরত্ব · প্রকাশিত অবস্থান' : 'Approximate straight-line distances · published locations only')
        : (bn ? '১০০ কিমির মধ্যে FoodPath-এ প্রকাশিত অবস্থান নেই। অন্য পুজো থাকতে পারে।' : 'No mapped FoodPath listing within 100 km of this location. Other Puja events may exist; browse a region instead.');
      for (const row of rows) {
        const li = doc.createElement('li'); const action = doc.createElement('button'); action.type = 'button'; action.className = 'button secondary';
        action.textContent = `${row.pandal.name} · ${row.distance.toFixed(1)} km`;
        action.addEventListener('click', () => select(row.pandal.pandal_id)); li.append(action); list.append(li);
      }
      // Only public Puja identities/distances remain; no user-coordinate state.
    }, error => { finish(); status.textContent = error.code === 1
      ? (bn ? 'অবস্থানের অনুমতি দেওয়া হয়নি। অঞ্চল বেছে খুঁজুন।' : 'Location permission was not granted. Choose a region to browse instead.')
      : (bn ? 'অবস্থান পাওয়া যায়নি। অঞ্চল বেছে খুঁজুন।' : 'Could not obtain a location. Choose a region to browse instead.');
    }, { enableHighAccuracy: false, timeout: 10000, maximumAge: 0 }); }
    catch { finish(); status.textContent = bn ? 'অবস্থান পাওয়া যায়নি। অঞ্চল বেছে খুঁজুন।' : 'Could not obtain a location. Choose a region to browse instead.'; }
  });
}

export function pujaLink(p, origin, language = 'en') {
  const url = new URL('/', origin); url.searchParams.set('region', p.region_id || 'kolkata'); url.searchParams.set('pandal', p.pandal_id);
  if (language === 'bn') url.searchParams.set('lang', 'bn');
  return url.href;
}
export function directionsURL(p) {
  if (!mapped(p) || p.coordinate_precision !== 'venue' || !p.edition?.venue_reviewed) return null;
  return 'https://www.google.com/maps/dir/?' + new URLSearchParams({ api: '1', destination: `${p.latitude},${p.longitude}` });
}
export function reportURL(p) {
  return 'https://github.com/shubha07m/food_safety/issues/new?' + new URLSearchParams({
    title: `Puja venue/date review: ${p.name}`, body: `Puja ID: ${p.pandal_id}\nRegion: ${p.region_id || 'kolkata'}\nName: ${p.name}\nSource: ${p.sources?.[0]?.source_url || ''}\n\nSuggested correction and supporting public source:\n`,
  });
}
export function freshnessLabels(p, checks, now = new Date()) {
  const labels = []; const e = p.edition;
  if (e?.confirmed && e.year === now.getFullYear()) labels.push(`${e.year} confirmed`);
  if (e?.venue_reviewed && e.year === now.getFullYear()) labels.push(`Venue reviewed for ${e.year}`);
  if (e?.start_date) labels.push([e.start_date, e.end_date !== e.start_date ? e.end_date : null].filter(Boolean).join(' – ') + ` · ${e.timezone}`);
  const sourceURLs = new Set((p.sources || []).map(s => s.source_url));
  const known = (checks || []).filter(c => sourceURLs.has(c.url));
  const latest = known.map(c => c.last_success).filter(Boolean).sort().at(-1);
  if (latest) labels.push(`Source checked ${latest.slice(0, 10)} · not edition verification`);
  if (known.some(c => c.pending_change)) labels.push('Source revision awaiting review');
  return labels;
}
export function addPujaActions(container, p, checks, bn = false) {
  for (let label of freshnessLabels(p, checks)) {
    if (bn) label = label.replace(/^(\d{4}) confirmed$/, '$1 সালের তথ্য নিশ্চিত')
      .replace(/^Venue reviewed for (\d{4})$/, '$1 সালের স্থান পর্যালোচিত')
      .replace('Source checked ', 'উৎস দেখা হয়েছে ').replace('not edition verification', 'বার্ষিক আয়োজনের নিশ্চয়তা নয়')
      .replace('Source revision awaiting review', 'উৎসের বর্তমান সংস্করণ পর্যালোচনার অপেক্ষায়');
    const line = document.createElement('p'); line.className = 'fine-print'; line.textContent = label; container.append(line);
  }
  const actions = document.createElement('div'); actions.className = 'puja-actions';
  const share = document.createElement('button'); share.type = 'button'; share.className = 'button secondary'; share.textContent = bn ? 'পুজোর লিঙ্ক শেয়ার করুন' : 'Share Puja';
  const status = document.createElement('span'); status.setAttribute('role', 'status'); status.className = 'fine-print';
  share.addEventListener('click', async () => {
    const url = pujaLink(p, location.origin, bn ? 'bn' : 'en');
    try {
      if (navigator.share) await navigator.share({ title: p.name, url });
      else if (navigator.clipboard?.writeText) { await navigator.clipboard.writeText(url); status.textContent = bn ? 'লিঙ্ক কপি হয়েছে' : 'Link copied'; }
      else { status.textContent = url; }
    } catch (error) { if (error.name !== 'AbortError') status.textContent = url; }
  });
  actions.append(share);
  for (const [label, url] of [[bn ? 'যাতায়াতের পথ' : 'Directions to reviewed venue', directionsURL(p)], [bn ? 'স্থান/তারিখ সংশোধন জানান' : 'Report changed venue/date', reportURL(p)]]) {
    if (!url) continue; const a = document.createElement('a'); a.href = url; a.textContent = label; a.className = 'button secondary'; a.target = '_blank'; a.rel = 'noopener noreferrer'; actions.append(a);
  }
  actions.append(status); container.append(actions);
}
