// The only Google runtime entry point. No Places library or restaurant coordinates.
export function scriptURL(key, language = 'en') {
  if (!/^AIza[A-Za-z0-9_-]{35}$/.test(key)) throw Error('Invalid browser configuration');
  return 'https://maps.googleapis.com/maps/api/js?' + new URLSearchParams({
    key, v: 'quarterly', loading: 'async', callback: 'foodpathMapLoaded', language: language === 'bn' ? 'bn' : 'en', auth_referrer_policy: 'origin',
  });
}
export function safeMarkers(markers) {
  if (!Array.isArray(markers)) return [];
  return markers.filter(m => m && ['area', 'pandal'].includes(m.kind) && typeof m.id === 'string'
    && typeof m.label === 'string' && Number.isFinite(m.lat) && Math.abs(m.lat) <= 90
    && Number.isFinite(m.lng) && Math.abs(m.lng) <= 180);
}
export function boot(win = window, doc = document) {
  if (win.parent === win || win.foodpathMapBooted) return;
  win.foodpathMapBooted = true;
  let map; let info; let markers = []; let started = false; let language = 'en'; let painted = ''; let selectedId = null; let markerStyle;
  let regionId = ''; let center = { lat: 22.57, lng: 88.36 }; let zoom = 11; let safetyContext = true;
  const notify = (type, extra = {}) => win.parent.postMessage({ type, ...extra }, win.location.origin);
  const fail = () => { doc.getElementById('map-error').hidden = false; notify('foodpath-map-error'); };
  win.gm_authFailure = fail;
  function overview() {
    if (!map) return;
    const focus = markers.some(m => m.kind === 'pandal') ? markers.filter(m => m.kind === 'pandal') : markers;
    const bounds = new win.google.maps.LatLngBounds();
    focus.forEach(m => bounds.extend({ lat: m.lat, lng: m.lng }));
    if (focus.length > 1) map.fitBounds(bounds, 40);
    else if (focus.length) { map.setCenter({ lat: focus[0].lat, lng: focus[0].lng }); map.setZoom(13); }
    else { map.setCenter(center); map.setZoom(zoom); }
  }
  function focusSelected() {
    const marker = markers.find(m => m.id === selectedId && m.kind === 'pandal');
    if (map && marker) { map.setCenter({ lat: marker.lat, lng: marker.lng }); map.setZoom(14); }
    else overview();
  }
  function paint() {
    if (!map) return;
    const signature = JSON.stringify([regionId, markers]); if (painted === signature) return; painted = signature;
    info?.close?.();
    map.data.forEach(f => map.data.remove(f));
    map.data.addGeoJson({ type: 'FeatureCollection', features: markers.map(m => ({ type: 'Feature', id: m.id,
      properties: { kind: m.kind, label: m.label, count: m.count }, geometry: { type: 'Point', coordinates: [m.lng, m.lat] } })) });
    focusSelected();
  }
  win.foodpathMapLoaded = () => {
    if (map) return;
    try {
      map = new win.google.maps.Map(doc.getElementById('map'), { center, zoom, maxZoom: 16,
        streetViewControl: false, mapTypeControl: false, fullscreenControl: true, clickableIcons: false, gestureHandling: 'cooperative' });
      info = new win.google.maps.InfoWindow();
      markerStyle = feature => ({ visible: doc.getElementById(feature.getProperty('kind') === 'area' ? 'areas-layer' : 'pandals-layer').checked,
        title: feature.getProperty('label'), icon: { path: feature.getProperty('kind') === 'area' ? win.google.maps.SymbolPath.CIRCLE : 'M 0,-7 7,0 0,7 -7,0 z',
          scale: feature.getProperty('kind') === 'area' ? 7 : (feature.getId() === selectedId ? 1.5 : 1), fillColor: feature.getProperty('kind') === 'area' ? '#426b7c' : '#a77422', fillOpacity: 1, strokeColor: feature.getId() === selectedId ? '#243536' : '#fff', strokeWeight: feature.getId() === selectedId ? 3 : 2 } });
      map.data.setStyle(markerStyle);
      for (const id of ['areas-layer', 'pandals-layer']) doc.getElementById(id).addEventListener('change', () => map.data.setStyle(markerStyle));
      map.data.addListener('click', event => {
        const feature = event.feature; const content = doc.createElement('div'); const heading = doc.createElement('h3'); heading.textContent = feature.getProperty('label'); content.append(heading);
        const notice = doc.createElement('p'); notice.textContent = language === 'bn' ? 'এলাকার আনুমানিক অবস্থান। রেস্তরাঁর সুরক্ষা নির্দেশক নয়।' : 'Coarse geographic anchor. Not an establishment address or safety rating.'; content.append(notice);
        if (feature.getProperty('kind') === 'area') {
          const button = doc.createElement('button'); button.textContent = language === 'bn' ? 'উৎসভিত্তিক নথি দেখুন' : `View ${feature.getProperty('count')} evidence records`;
          button.addEventListener('click', () => notify('foodpath-map-select', { id: feature.getId() })); content.append(button);
        } else {
          const button = doc.createElement('button'); button.textContent = language === 'bn' ? 'মণ্ডপের তথ্য দেখুন' : 'View pandal links';
          button.addEventListener('click', () => notify('foodpath-map-select', { id: feature.getId() })); content.append(button);
        }
        info.setContent(content); info.setPosition(event.latLng); info.open({ map });
      });
      paint(); notify('foodpath-map-loaded');
    } catch { fail(); }
  };
  win.addEventListener('message', event => {
    if (event.source !== win.parent || event.origin !== win.location.origin) return;
    if (event.data?.type === 'foodpath-map-focus') {
      selectedId = event.data.id || null;
      if (map) { map.data.setStyle(markerStyle); focusSelected(); }
      return;
    }
    if (event.data?.type !== 'foodpath-map-data') return;
    regionId = event.data.regionId || '';
    const c = event.data.mapCenter;
    if (Number.isFinite(c?.lat) && Math.abs(c.lat) <= 90 && Number.isFinite(c?.lng) && Math.abs(c.lng) <= 180) center = c;
    if (Number.isInteger(event.data.mapZoom) && event.data.mapZoom >= 1 && event.data.mapZoom <= 16) zoom = event.data.mapZoom;
    safetyContext = event.data.safetyContext !== false;
    const areaToggle = doc.getElementById('areas-layer');
    if (!safetyContext) areaToggle.checked = false;
    areaToggle.disabled = !safetyContext;
    if (areaToggle.parentElement) areaToggle.parentElement.hidden = !safetyContext;
    markers = safeMarkers(event.data.markers).filter(m => safetyContext || m.kind !== 'area'); language = event.data.language; selectedId = event.data.selectedPandalId || null;
    if (started) { paint(); return; }
    started = true;
    try { const script = doc.createElement('script'); script.src = scriptURL(event.data.key, language); script.async = true; script.referrerPolicy = 'origin'; script.onerror = fail; doc.head.append(script); } catch { fail(); }
  });
  notify('foodpath-map-ready');
}
if (typeof window !== 'undefined' && typeof document !== 'undefined') boot();
