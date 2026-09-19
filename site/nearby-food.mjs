// Static provider composition only. No discovery/geocoding/provider HTTP calls.
import { foodMapsURL } from './maps-handoff.mjs';
const osmID = /^osm:(node|way|relation):[1-9][0-9]*$/;
const googleID = /^[A-Za-z0-9_-]{1,255}$/;
const categories = new Set(['restaurant', 'cafe', 'fast_food', 'ice_cream', 'food_court', 'bakery', 'confectionery']);
export const INITIAL_FOOD_LIMIT = 12;
export const MAX_FOOD_LIMIT = 20;
const normalizedName = value => String(value || '').normalize('NFC').trim().replace(/\s+/g, ' ').toLowerCase();
const compareText = (a, b) => a < b ? -1 : a > b ? 1 : 0;
export function mappedPandal(p) {
  return p.enabled !== false && !!p.coordinate_source && Number.isFinite(p.latitude) && Number.isFinite(p.longitude)
    && Math.abs(p.latitude) <= 90 && Math.abs(p.longitude) <= 180;
}
export function publicFood(data, pandal) {
  const all = data.groups.get(pandal.pandal_id) || [];
  const seen = new Set();
  const named = mappedPandal(pandal) ? all.filter(row => row.provider === 'osm' && osmID.test(row.id)
    && typeof row.name === 'string' && /\p{L}/u.test(row.name)
    && !['unnamed', 'unknown', 'n/a', 'no name', 'unnamed food place', 'restaurant on google maps'].includes(normalizedName(row.name))
    && Number.isFinite(row.distance) && row.distance >= 0)
    .sort((a, b) => a.distance - b.distance || compareText(normalizedName(a.name), normalizedName(b.name)) || compareText(a.id, b.id))
    .filter(row => { if (seen.has(row.id)) return false; seen.add(row.id); return true; }) : [];
  return { rows: named.slice(0, MAX_FOOD_LIMIT), named_public_count: Math.min(named.length, MAX_FOOD_LIMIT),
    named_snapshot_count: named.length,
    historical_google_association_count: data.historicalGoogleCounts?.get(pandal.pandal_id)
      ?? new Set(all.filter(r => r.provider !== 'osm').map(r => r.id)).size };
}
export function foodGeography(data) {
  return data.pandals.filter(mappedPandal).map(pandal => ({ pandal, count: publicFood(data, pandal).named_snapshot_count }))
    .sort((a, b) => compareText(normalizedName(a.pandal.name), normalizedName(b.pandal.name)) || compareText(a.pandal.pandal_id, b.pandal.pandal_id));
}
export function pandalFoodURL(pandal) {
  if (!mappedPandal(pandal)) return null;
  const query = `restaurants near ${pandal.latitude.toFixed(7)},${pandal.longitude.toFixed(7)}`;
  return `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query })}`;
}
export function osmMapsURL(poi, placeID = null, locality = []) {
  return osmID.test(poi.poi_id) ? foodMapsURL(poi, { locality, verifiedPlaceID: placeID }) : null;
}

export function combineFood(legacy, osm, policy) {
  if (!policy || policy.schema_version !== 'food-provider-1' || !['osm', 'google', 'hybrid'].includes(policy.provider)) return legacy;
  const mode = policy.provider;
  const result = { ...legacy, provider: mode, displayLimit: Math.max(10, Math.min(15, policy.initial_display_limit || 15)), osmCoverage: new Map(),
    historicalGoogleCounts: new Map([...legacy.groups].map(([id, rows]) => [id, new Set(rows.map(r => r.id)).size])) };
  if (mode === 'google') return result;
  if (!osm || osm.schema_version !== 'food-osm-1' || osm.license !== 'ODbL-1.0'
    || osm.attribution_url !== 'https://www.openstreetmap.org/copyright'
    || !Array.isArray(osm.pois) || !Array.isArray(osm.associations)) return legacy;
  const pois = new Map(); const links = new Map(); const usedIDs = new Set();
  const rawPois = new Map(osm.pois.map(p => [p.poi_id, p]));
  const anchors = new Map(legacy.pandals.map(p => [p.pandal_id, p]));
  for (const link of policy.google_links || []) {
    if ((link.status && link.status !== 'verified') || !osmID.test(link.poi_id) || !googleID.test(link.place_id) || !link.identity_source || !link.verified_at
      || links.has(link.poi_id) || usedIDs.has(link.place_id)) throw Error('Ambiguous food identity link');
    links.set(link.poi_id, link.place_id); usedIDs.add(link.place_id);
  }
  for (const poi of osm.pois) {
    if (poi.provider !== 'osm' || !osmID.test(poi.poi_id) || !categories.has(poi.category)
      || poi.poi_id !== `osm:${poi.osm_type}:${poi.osm_id}`
      || poi.source_url !== `https://www.openstreetmap.org/${poi.osm_type}/${poi.osm_id}`
      || !osmMapsURL(poi) || pois.has(poi.poi_id)) throw Error('Invalid OSM food record');
    pois.set(poi.poi_id, { id: poi.poi_id, name: typeof poi.name === 'string' ? poi.name : null,
      name_bn: poi.name_bn, category: poi.category, cuisine: poi.cuisine,
      provider: 'osm', url: osmMapsURL(poi, links.get(poi.poi_id)),
      at: (osm.snapshot_date || osm.extracted_at || '').slice(0, 10),
      source: poi.source_url, googleID: links.get(poi.poi_id) });
  }
  const groups = new Map(); const seen = new Set();
  const pandals = new Set(legacy.pandals.map(p => p.pandal_id));
  for (const row of osm.coverage || []) {
    if (pandals.has(row.pandal_id) && row.status === 'snapshot') result.osmCoverage.set(row.pandal_id, row);
  }
  for (const a of osm.associations) {
    const key = `${a.pandal_id}/${a.poi_id}`;
    if (a.provider !== 'osm' || a.source_snapshot !== osm.snapshot_id || !Number.isFinite(a.distance_m)
      || a.distance_m < 0 || !pois.has(a.poi_id)) throw Error('Invalid OSM association');
    if (!pandals.has(a.pandal_id) || seen.has(key)) continue;
    if (!result.osmCoverage.has(a.pandal_id) || a.distance_m > result.osmCoverage.get(a.pandal_id).radius_m) throw Error('Invalid OSM catchment');
    const rows = groups.get(a.pandal_id) || [];
    const anchor = anchors.get(a.pandal_id);
    const locality = [anchor.neighborhood, anchor.area, anchor.city, anchor.admin1, anchor.country_code];
    rows.push({ ...pois.get(a.poi_id), distance: a.distance_m,
      url: osmMapsURL(rawPois.get(a.poi_id), links.get(a.poi_id), locality) });
    groups.set(a.pandal_id, rows); seen.add(key);
  }
  for (const rows of groups.values()) rows.sort((a, b) => a.distance - b.distance || (a.name || '').localeCompare(b.name || '') || a.id.localeCompare(b.id));
  if (mode === 'hybrid') {
    for (const [id, googleRows] of legacy.groups) {
      const osmRows = groups.get(id) || [];
      const matched = new Set(osmRows.map(r => r.googleID).filter(Boolean));
      groups.set(id, [...osmRows, ...googleRows.filter(r => !matched.has(r.id)).map(r => ({ ...r, provider: 'google' }))]);
    }
  }
  return { ...result, groups };
}
