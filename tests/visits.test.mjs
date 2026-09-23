import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { VisitCounter, allowed } from '../worker/visits.mjs';
import { visitCount } from '../site/visits.mjs';
const store = () => { const rows=new Map(); return {getItem:k=>rows.get(k),setItem:(k,v)=>rows.set(k,v)}; };
const request = (overrides={}) => new Request('https://food.example/api/visits', {method:'POST',body:'{}',headers:{Origin:'https://food.example','Sec-Fetch-Site':'same-origin','Content-Type':'application/json','Content-Length':'2','X-FoodPath-Visit':'1'},...overrides});
test('one increment per tab session; new session increments; no identifying payload', async()=>{
  const seen=[]; const fetcher=async(url,options)=>{seen.push([url,options]);return Response.json({count:12});}; const storage=store();
  assert.equal(await visitCount({fetcher,storage}),12); await visitCount({fetcher,storage}); await visitCount({fetcher,storage:store()});
  assert.deepEqual(seen.map(x=>x[1].method),['POST','GET','POST']);
  assert.equal(seen[0][1].body,'{}'); assert.equal(seen[0][1].credentials,'omit'); assert.equal(seen[0][0],'/api/visits');
});
test('missing endpoint/storage failures degrade without retries',async()=>{
  const storage=store(); let calls=0; const fetcher=async()=>{calls++;throw Error('offline');};
  assert.equal(await visitCount({fetcher,storage}),null); assert.equal(calls,1);
  assert.equal(await visitCount({storage:{getItem(){throw Error('blocked');}},fetcher:async(u,o)=>{assert.equal(o.method,'GET');return new Response('',{status:404});}}),null);
});
test('malformed and cross-origin writes rejected, GET safe', async()=>{
  assert.ok(allowed(new Request('https://food.example/api/visits'))); assert.ok(allowed(request()));
  for(const req of [request({method:'PUT'}),request({headers:{Origin:'https://evil.example'}}),new Request('https://food.example/api/visits?x=1')]) assert.equal((await worker.fetch(req,{})).status,400);
  assert.equal((await worker.fetch(request({body:'[]'}),{})).status,400);
  assert.equal((await worker.fetch(request(),{})).status,503);
});
test('aggregate stores count and time buckets only; write caps and failure handling',async()=>{
  let saved; const tx={get:async()=>saved,put:async(k,v)=>{assert.equal(k,'aggregate');saved=v;}};
  const counter=new VisitCounter({storage:{transaction:fn=>fn(tx)}});
  for(let i=0;i<65;i++) await counter.fetch(new Request('https://internal',{method:'POST'}));
  assert.equal(saved.count,60); assert.deepEqual(Object.keys(saved).sort(),['count','daily','day','minute','recent']);
  assert.equal((await (await counter.fetch(new Request('https://internal'))).json()).count,60);
  const broken=new VisitCounter({storage:{transaction(){throw Error('offline');}}}); assert.equal((await broken.fetch(new Request('https://internal'))).status,503);
});
test('edge forwards no client metadata and static requests bypass counter',async()=>{
  const env={VISITS:{idFromName:()=>1,get:()=>({fetch:async r=>{assert.equal([...r.headers].length,0);assert.equal(r.method,'POST');return Response.json({count:2});}})},ASSETS:{fetch:async()=>new Response('static')}};
  assert.equal((await (await worker.fetch(request(),env)).json()).count,2);
  assert.equal(await (await worker.fetch(new Request('https://food.example/'),env)).text(),'static');
});
