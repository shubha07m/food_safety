// Static search shortcuts are not POIs and never enter association/counting logic.
export function regionalSearches(region) {
  return (region.regional_food_searches || []).map(row => {
    if (row.type !== 'regional_food_search' || row.region_id !== region.region_id
      || row.provider !== 'Google Maps' || typeof row.query !== 'string' || !row.query.trim()
      || typeof row.label !== 'string' || !row.label.trim()) throw Error('Invalid regional food search');
    const url = `https://www.google.com/maps/search/?${new URLSearchParams({ api: '1', query: row.query })}`;
    if (row.maps_url !== url) throw Error('Invalid regional handoff');
    return { ...row, url };
  });
}
export function foodView(search, region) {
  return regionalSearches(region).length && new URLSearchParams(search).get('view') === 'bengali-food'
    ? 'bengali-food' : 'puja';
}
