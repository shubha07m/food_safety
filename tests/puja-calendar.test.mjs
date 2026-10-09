import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { calendarGroups, calendarRange, californiaToday, renderCalendar } from '../site/puja-calendar.mjs';
import { effectiveLocation, publicationLabel } from '../site/puja-location.mjs';
const evidence = { source_url:'https://example.org/puja', quote:'Durga Puja October 16–20, 2026' };
const dates = {start_date:'2026-10-16',end_date:'2026-10-20',timezone:'America/Los_Angeles',reviewed_at:'2026-10-09T08:00:00Z',evidence:[evidence]};
const p = {pandal_id:'test-puja',region_id:'california',name:'Fixture Puja',sources:[evidence],reviewed_dates:dates};
test('reviewed dates qualify without a venue or an edition',()=>{
  assert.equal(calendarGroups([p],'2026-10-09').length,1);
  assert.deepEqual(effectiveLocation(p,2026),effectiveLocation({...p,reviewed_dates:null},2026));
  assert.equal(publicationLabel(p,2026),'Source-listed · current venue not reviewed');
});
test('legacy claims, missing evidence, identity attestation and unrelated sources excluded',()=>{
  for(const change of [null,{...dates,evidence:[]},{...dates,evidence:[{...evidence,evidence_kind:'owner_attestation'}]},{...dates,evidence:[{...evidence,source_url:'https://other.example'}]}]) {
    assert.equal(calendarGroups([{...p,reviewed_dates:change,event_dates:'October 16–20, 2026'}],'2026-10-09').length,0);
  }
});
test('malformed dates, reversed ranges, wrong timezone, disabled and other regions excluded',()=>{
  for(const reviewed_dates of [{...dates,start_date:'2026-02-30'},{...dates,end_date:'bad'},{...dates,end_date:'2026-10-15'},{...dates,timezone:'UTC'},{...dates,reviewed_at:null}]) assert.equal(calendarGroups([{...p,reviewed_dates}],'2026-01-01').length,0);
  assert.deepEqual(calendarGroups([{...p,region_id:'kolkata'},{...p,enabled:false}],'2026-10-09'),[]);
});
test('full ranges stay intact across weekends and stable IDs count once',()=>{
  const a={...p,reviewed_dates:{...dates,end_date:'2026-10-27'}};
  const b={...a,pandal_id:'second'};
  const groups=calendarGroups([a,a,b],'2026-10-18');
  assert.equal(groups.length,1); assert.equal(groups[0].entries.length,2);
  assert.equal(groups[0].end,'2026-10-27'); assert.equal(groups[0].ongoing,true);
  assert.match(calendarRange(groups[0].start,groups[0].end),/27/);
});
test('California date is independent of UTC rollover and daylight saving',()=>{
  assert.equal(californiaToday(new Date('2026-10-17T01:00:00Z')),'2026-10-16');
  assert.equal(californiaToday(new Date('2027-01-01T07:59:00Z')),'2026-12-31');
  assert.equal(californiaToday(new Date('2027-01-01T08:00:00Z')),'2027-01-01');
});
test('past dates disappear, future and cross-year ranges remain exact',()=>{
  assert.equal(calendarGroups([p],'2026-10-21').length,0);
  const future={...p,reviewed_dates:{...dates,start_date:'2026-12-31',end_date:'2027-01-02'}};
  assert.equal(calendarGroups([future],'2027-01-01')[0].ongoing,true);
  assert.equal(calendarGroups([future],'2027-01-03').length,0);
});
test('confirmed structured edition dates can supply calendar; unconfirmed cannot',()=>{
  assert.equal(calendarGroups([{...p,reviewed_dates:null,edition:{...dates,confirmed:true}}],'2026-10-09').length,1);
  assert.equal(calendarGroups([{...p,reviewed_dates:null,edition:{...dates,confirmed:false}}],'2026-10-09').length,0);
});
class Element {
  constructor(tag) { this.tag=tag; this.children=[]; this.attributes={}; this.listeners={}; }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children=children; }
  setAttribute(k,v) {this.attributes[k]=v;}
  addEventListener(k,v) {this.listeners[k]=v;}
}
const doc={createElement:tag=>new Element(tag)};
const flatten=n=>[n,...n.children.flatMap(flatten)];
test('California-only semantic panel and selection reuse',()=>{
  const host=new Element('section'); let selected;
  renderCalendar(host,[p],'california',id=>selected=id,{doc,today:'2026-10-09'});
  assert.equal(host.hidden,false);
  const button=flatten(host).find(n=>n.tag==='button'); button.listeners.click(); assert.equal(selected,p.pandal_id);
  assert.equal(button.type,'button');
  renderCalendar(host,[p],'london',()=>{},{doc}); assert.equal(host.hidden,true); assert.equal(host.children.length,0);
});
test('Bengali dates, labels and empty state',()=>{
  const host=new Element('section');
  renderCalendar(host,[p],'california',()=>{},{doc,bn:true,today:'2026-10-09'});
  assert.match(flatten(host).map(n=>n.textContent).join(' '),/ক্যালিফোর্নিয়ার|আসন্ন/);
  assert.match(calendarRange(dates.start_date,dates.end_date,true),/২০২৬/);
  renderCalendar(host,[],'california',()=>{},{doc,bn:true});
  assert.match(flatten(host).map(n=>n.textContent).join(' '),/এখনও পাওয়া যায়নি/);
});
test('published California eligibility has exactly three supported ranges; no edition promotion',()=>{
  const records=JSON.parse(readFileSync('site/data/pandals.json')).records;
  const groups=calendarGroups(records,'2026-10-09');
  assert.deepEqual(groups.map(g=>[g.start,g.end,g.entries.map(e=>e.pandal.pandal_id)]),[
    ['2026-10-16','2026-10-18',['ca-agomoni']],['2026-10-16','2026-10-20',['ca-pashchimi']],['2026-10-23','2026-10-25',['ca-ankur']],
  ]);
  for(const g of groups) for(const e of g.entries) assert.equal(e.pandal.edition,null);
});
