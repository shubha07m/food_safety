// Region configuration is generated from the operator registry, not browser APIs.
export function parseRegions(raw) {
  if (raw?.schema_version !== 'puja-regions-1' || !Array.isArray(raw.regions) || !raw.regions.length) throw Error('Invalid region registry');
  const seen = new Set();
  for (const r of raw.regions) {
    if (!/^[a-z0-9_-]+$/.test(r.region_id) || seen.has(r.region_id)
      || !['osm', 'google', 'hybrid'].includes(r.food_provider_mode)
      || ![r.food_data, r.provider_data].every(p => /^data\/[a-z0-9_-]+\.json$/.test(p))
      || !Number.isFinite(r.default_map_center?.lat) || Math.abs(r.default_map_center.lat) > 90
      || !Number.isFinite(r.default_map_center?.lng) || Math.abs(r.default_map_center.lng) > 180
      || !Number.isInteger(r.default_map_zoom) || r.default_map_zoom < 1 || r.default_map_zoom > 16) throw Error('Invalid region');
    seen.add(r.region_id);
  }
  if (!seen.has(raw.default_region)) throw Error('Invalid default region');
  return raw;
}
export function regionFromURL(search, registry) {
  const params = new URLSearchParams(search);
  const requested = params.get('module') === 'safety' || params.has('event') ? registry.default_region : params.get('region');
  return registry.regions.find(r => r.region_id === requested) || registry.regions.find(r => r.region_id === registry.default_region);
}
export function scopeFood(data, region, defaultRegion) {
  const pandals = data.pandals.filter(p => (p.region_id || defaultRegion) === region.region_id);
  const ids = new Set(pandals.map(p => p.pandal_id));
  const scoped = { ...data, pandals, index: data.index.filter(r => ids.has(r.p.pandal_id)) };
  for (const key of ['groups', 'discoveries', 'osmCoverage', 'historicalGoogleCounts']) {
    scoped[key] = new Map([...(data[key] || [])].filter(([id]) => ids.has(id)));
  }
  return scoped;
}
export function regionURL(href, regionId, pandals) {
  const url = new URL(href); url.searchParams.set('region', regionId);
  if (!pandals.some(p => p.pandal_id === url.searchParams.get('pandal'))) url.searchParams.delete('pandal');
  return url;
}
