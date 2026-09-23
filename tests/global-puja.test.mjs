import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { mapped, nearestPujas, distanceKm, resolvePuja, initNearMe, directionsURL, pujaLink, reportURL, freshnessLabels } from '../site/global-puja.mjs';
import { scopeMarkers, pandalMarkers } from '../site/map-host.mjs';
const p = (id, lat, lng, region = 'london') => ({ pandal_id: id, name: id, region_id: region, latitude: lat, longitude: lng, coordinate_source: 'https://example.org/venue', coordinate_precision: 'venue', edition: { venue_reviewed: true } });
test('local Haversine and bounded nearest ordering across all regions', () => {
  const rows = [p('a', 51.51, 0), p('b', 51.5, 0), p('far', -37, 144, 'melbourne'), { name: 'unmapped' }];
  assert.ok(distanceKm(rows[0], rows[1]) > 1 && distanceKm(rows[0], rows[1]) < 1.2);
  assert.deepEqual(nearestPujas(rows, { latitude:51.5, longitude:0 }).map(r=>r.pandal.pandal_id), ['b','a']);
  assert.deepEqual(nearestPujas(rows, {latitude:0, longitude:0}), []);
  assert.deepEqual(nearestPujas(rows, {latitude:100, longitude:0}), []);
  assert.ok(!mapped({...rows[0], coordinate_source:null}));
});
test('one global resolver supports world, Near Me and local selection', () => {
  const regions = [{region_id:'london'},{region_id:'melbourne'}]; const rows = [p('a',51,0), p('b',-37,144,'melbourne')];
  assert.equal(resolvePuja(rows,regions,'b').region.region_id,'melbourne');
  assert.equal(resolvePuja(rows,regions,'missing'),null);
  const markers = pandalMarkers(rows); const areas=[{kind:'area'}];
  assert.deepEqual(scopeMarkers(markers.slice(0,1),markers,areas,'world',true),markers);
  assert.equal(scopeMarkers(markers.slice(0,1),markers,areas,'region',true).length,2);
  assert.equal(scopeMarkers(markers.slice(0,1),markers,areas,'region',false).length,1);
});
test('location only requested on click, once while pending; errors restore control', () => {
  const nodes = Object.fromEntries(['puja-near-me','near-me-status','near-me-results'].map(id=>[id,{handlers:{},addEventListener(k,v){this.handlers[k]=v;},replaceChildren(){}}]));
  const doc={getElementById:id=>nodes[id]}; let calls=0; let fail;
  initNearMe([],()=>{}, {doc,geo:{getCurrentPosition(ok,error,options){calls++;fail=error;assert.equal(options.maximumAge,0);}}});
  assert.equal(calls,0); nodes['puja-near-me'].handlers.click(); nodes['puja-near-me'].handlers.click(); assert.equal(calls,1);
  fail({code:1}); assert.match(nodes['near-me-status'].textContent,/permission/); assert.equal(nodes['puja-near-me'].disabled,false);
  nodes['puja-near-me'].handlers.click(); fail({code:2}); assert.match(nodes['near-me-status'].textContent,/Could not/);
  const source=readFileSync('site/global-puja.mjs','utf8');
  assert.doesNotMatch(source,/watchPosition|localStorage|sessionStorage|fetch\(/);
});
test('directions only reviewed precise venue; shared links have no user coordinates', () => {
  const row=p('a',51,0); const url=new URL(directionsURL(row)); assert.equal(url.searchParams.get('destination'),'51,0');
  assert.equal(directionsURL({...row,coordinate_precision:'street'}),null);
  assert.equal(directionsURL({...row,edition:null}),null);
  const link=new URL(pujaLink(row,'https://example.org')); assert.equal(link.searchParams.get('pandal'),'a'); assert.equal(link.searchParams.size,2);
  assert.match(new URL(reportURL(row)).searchParams.get('body'),/Region: london/);
});
test('source checks cannot imply current-year confirmation', () => {
  const row={year:2026,sources:[{source_url:'https://example.org'}]};
  const checked=[{url:'https://example.org',last_success:'2026-09-22T00:00:00Z',pending_change:true}];
  assert.ok(!freshnessLabels(row,checked).some(s=>s.includes('confirmed')));
  assert.match(freshnessLabels(row,checked).join(' '),/awaiting review/);
  assert.ok(freshnessLabels({...row,edition:{year:2026,confirmed:true}},[],new Date('2026-09-22')).includes('2026 confirmed'));
});
