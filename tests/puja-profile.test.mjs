import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { effectiveLocation, publicationLabel } from '../site/puja-location.mjs';
import { profileView, renderProfile } from '../site/puja-profile.mjs';
import { pandalMarkers } from '../site/map-host.mjs';
import { nearestPujas, directionsURL } from '../site/global-puja.mjs';
import { combineFood } from '../site/nearby-food.mjs';
const year = new Date().getUTCFullYear();
test('shared static/operator effective location contract',()=>{
  for(const c of JSON.parse(readFileSync('tests/fixtures/puja_locations.json','utf8'))) {
    const result=effectiveLocation(c.record,2026);
    assert.deepEqual(Object.fromEntries(Object.keys(c.expected).map(k=>[k,result[k]])),c.expected,c.label);
  }
});
const loc = {venue:'Reviewed Hall',address:'1 Fixture Street',latitude:51.5,longitude:0,coordinate_source:'https://example.org/venue',coordinate_precision:'venue'};
const evidence = {source_url:'https://example.org',source_title:'Organizer',publisher:'Fixture',quote:'Fixture Durga Puja'};
const p = {pandal_id:'fixture',name:'Fixture Puja',region_id:'london',city:'London',...loc,sources:[evidence],edition:{year,confirmed:true,venue_reviewed:true,location:loc,start_date:`${year}-10-17`,timezone:'Europe/London'}};
test('two derived tiers never promote a fetch or unsupported date/venue',()=>{
  assert.match(publicationLabel({...p,edition:null}),/^Source-listed/);
  assert.match(publicationLabel({...p,edition:{...p.edition,location:null}}),/event confirmed/);
  assert.match(publicationLabel(p),/venue\/date reviewed/);
  assert.match(publicationLabel(p,year+1),/^Source-listed/);
});
test('edition anchor is atomic across world map, Near Me and directions',()=>{
  const moved={...p,edition:{...p.edition,location:{...loc,latitude:52}}};
  assert.equal(pandalMarkers([moved])[0].lat,52);
  assert.equal(nearestPujas([moved],{latitude:52,longitude:0})[0].distance,0);
  assert.equal(new URL(directionsURL(moved)).searchParams.get('destination'),'52,0');
  for (const edition of [{...p.edition,location:null},{...p.edition,year:year-1}]) {
    const stale={...p,edition}; assert.equal(pandalMarkers([stale]).length,0);
    assert.equal(nearestPujas([stale],{latitude:51.5,longitude:0}).length,0);
    assert.equal(directionsURL(stale),null);
  }
  const approximate={...p,edition:{...p.edition,location:{...loc,coordinate_precision:'street'}}};
  assert.equal(pandalMarkers([approximate]).length,1);
  assert.equal(nearestPujas([approximate],{latitude:51.5,longitude:0}).length,0);
  assert.equal(directionsURL(approximate),null);
});
test('missing override coordinates do not inherit previous venue; historical facts stay labelled',()=>{
  const next={...p,edition:{...p.edition,location:{venue:'New hall',address:'New address'}}};
  assert.equal(effectiveLocation(next).map_eligible,false);
  assert.equal(effectiveLocation(next).venue,'New hall');
  assert.equal(effectiveLocation(p,year+1).status,'historical');
});
test('profile hides stale programme notes and absent optional facts',()=>{
  const notes=[{title:'Programme',text:'Fixture',evidence:[evidence]}];
  const rich={...p,edition:{...p.edition,programme_notes:notes},official_links:[{kind:'website',url:'https://example.org',evidence}]};
  assert.equal(profileView(rich,{label:'London'}).notes.length,1);
  assert.equal(profileView(rich,{label:'London'},[],year+1).notes.length,0);
  assert.equal(profileView({...p,edition:null},{label:'London'}).dates,null);
  assert.equal(profileView({...p,official_links:[{kind:'website',url:'javascript:alert(1)',evidence}]},{label:'London'}).links.length,0);
});
test('moved-edition food ignores a snapshot associated against the old anchor',()=>{
  const moved={...p,edition:{...p.edition,location:{...loc,latitude:52}}};
  const legacy={pandals:[moved],groups:new Map()};
  const osm={schema_version:'food-osm-1',license:'ODbL-1.0',attribution_url:'https://www.openstreetmap.org/copyright',snapshot_id:'s',pois:[],associations:[],coverage:[{pandal_id:'fixture',status:'snapshot',radius_m:600,anchor_key:'51.5000000,0.0000000'}]};
  assert.equal(combineFood(legacy,osm,{schema_version:'food-provider-1',provider:'osm'}).osmCoverage.size,0);
  osm.coverage[0].anchor_key='52.0000000,0.0000000';
  assert.equal(combineFood(legacy,osm,{schema_version:'food-provider-1',provider:'osm'}).osmCoverage.size,1);
});
// Minimal DOM fixture tests semantic structure without adding a browser framework.
class Element {
  constructor(tag){this.tag=tag;this.children=[];this.textContent='';this.attributes={};}
  append(...items){this.children.push(...items);}
  setAttribute(k,v){this.attributes[k]=v;}
  addEventListener(){}
}
const doc={createElement:tag=>new Element(tag),createTextNode:text=>({textContent:text,children:[]})};
const flatten=n=>[n,...n.children.flatMap(flatten)];
test('owner endorsement is not rendered as an organizer quotation',()=>{
  const source={...evidence,evidence_kind:'owner_attestation',quote:'Owner approved submitted identity.'};
  const text=flatten(renderProfile({...p,edition:null,sources:[source]}, {label:'London'},[],false,doc))
    .map(n=>n.textContent).join(' ');
  assert.match(text,/Owner review: Owner approved submitted identity/);
  assert.ok(!text.includes('“Owner approved'));
});
test('profile article, actions, nested provenance and programme are not restaurant rows',()=>{
  const rich={...p,about:{text:'Source-backed introduction',evidence:[evidence]},organizer:'Fixture Association',official_links:[{kind:'website',url:'https://example.org',evidence}],edition:{...p.edition,programme_notes:[{title:'Music',text:'Sourced concert',evidence:[evidence]}]}};
  const card=renderProfile(rich,{label:'London'},[],false,doc); const nodes=flatten(card); const text=nodes.map(n=>n.textContent).join(' ');
  assert.equal(card.tag,'article'); assert.match(text,/Reviewed Hall/); assert.match(text,/1 Fixture Street/);
  for(const label of ['Directions','Official site','Share Puja','Report changed venue/date','More about this Puja','Read source provenance','Music']) assert.ok(text.includes(label));
  assert.equal(nodes.filter(n=>n.tag==='details').length,2);
  assert.ok(!text.includes('Nearby food'));
  const sparse=flatten(renderProfile({...p,edition:null},{label:'London'},[],true,doc)).map(n=>n.textContent).join(' ');
  assert.ok(!sparse.includes('undefined') && !sparse.includes('null'));
});
