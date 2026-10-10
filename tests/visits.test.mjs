import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import worker, { VisitCounter, allowed } from '../worker/visits.mjs';
import { visitCount, visitCopy, initVisits } from '../site/visits.mjs';
const store = () => { const rows=new Map(); return {getItem:k=>rows.get(k),setItem:(k,v)=>rows.set(k,v)}; };
test('dynamic human wording and Bengali description',()=>{
  assert.equal(visitCopy(12483).label,'12,483 site visits and counting');
  assert.match(visitCopy(59,true).label,/৫৯ সাইট ভিজিট/);
  assert.match(visitCopy(59,true).description,/মানুষের সংখ্যা নয়/);
});
test('counter does not block rendering and waits for a visible page; failure stays hidden',async()=>{
  const node={hidden:true}; const callbacks={}; let task; let calls=0;
  const doc={visibilityState:'hidden',documentElement:{lang:'bn'},getElementById:()=>node,
    addEventListener:(k,fn)=>callbacks[k]=fn,removeEventListener:k=>delete callbacks[k]};
  const deps={countVisit:async()=>{calls++;return null;},schedule:(fn,ms)=>{assert.equal(ms,1500);task=fn;}};
  initVisits(doc,deps); assert.equal(task,undefined); assert.equal(calls,0);
  doc.visibilityState='visible';callbacks.visibilitychange(); assert.equal(calls,0);
  await task(); assert.equal(calls,1); assert.equal(node.hidden,true);
  initVisits(doc,{...deps,countVisit:async()=>59}); await task();
  assert.equal(node.hidden,false); assert.match(node.textContent,/৫৯/); assert.match(node.title,/মানুষের/);
});
const request = (overrides={}) => new Request('https://food.example/api/visits', {method:'POST',body:'{}',headers:{Origin:'https://food.example','Sec-Fetch-Site':'same-origin','Content-Type':'application/json','Content-Length':'2','X-FoodPath-Visit':'1'},...overrides});
test('one increment per tab session; new session increments; no identifying payload', async()=>{
  const seen=[]; const fetcher=async(url,options)=>{seen.push([url,options]);return Response.json({count:12});}; const storage=store();
  assert.equal(await visitCount({fetcher,storage}),12); await visitCount({fetcher,storage}); await visitCount({fetcher,storage:store()});
  assert.deepEqual(seen.map(x=>x[1].method),['POST','GET','POST']);
  assert.equal(seen[0][1].body,'{}'); assert.equal(seen[0][1].credentials,'omit'); assert.equal(seen[0][0],'/api/visits');
});
test('missing endpoint/storage failures degrade without retries',async()=>{
  const storage=store(); let calls=0; const fetcher=async()=>{calls++;throw Error('offline');};
  assert.equal(await visitCount({fetcher,storage}),null); assert.equal(calls,2);
  assert.equal(await visitCount({storage:{getItem(){throw Error('blocked');}},fetcher:async(u,o)=>{assert.equal(o.method,'GET');return new Response('',{status:404});}}),null);
});
test('counter initializes before unrelated app initialization awaits',()=>{
  const app=readFileSync(new URL('../site/app.js',import.meta.url),'utf8');
  assert.equal(app.split('initVisits();').length,2);
  assert.ok(app.indexOf('initVisits();') < app.indexOf('initPuja(setMapPandals)'));
  assert.ok(app.indexOf('initVisits();') < app.indexOf('await Promise.all'));
});
test('failed POST permits one GET fallback; receipt prevents repeated writes',async()=>{
  for(const failure of ['network','http','json','invalid']) {
    const methods=[];const storage=store();
    const fetcher=async(url,o)=>{
      methods.push(o.method);
      assert.equal(o.credentials,'omit'); assert.equal(o.cache,'no-store');
      if(o.method==='GET') { assert.equal(o.body,undefined); return Response.json({count:59}); }
      assert.equal(storage.getItem('foodpath-visit-v1'),'sent');
      if(failure==='network')throw Error('offline');
      if(failure==='http')return new Response('',{status:503});
      if(failure==='json')return new Response('not JSON');
      return Response.json({count:-1});
    };
    assert.equal(await visitCount({fetcher,storage}),59);
    assert.deepEqual(methods,['POST','GET']);
    assert.equal(await visitCount({fetcher,storage}),59);
    assert.deepEqual(methods,['POST','GET','GET']);
  }
});
test('unavailable storage is GET-only, including failed reads',async()=>{
  for(const operation of ['getItem','setItem']) {
    const storage={...store(),[operation](){throw Error('blocked');}};
    const methods=[];
    assert.equal(await visitCount({storage,fetcher:async(u,o)=>{methods.push(o.method);return Response.json({count:0});}}),0);
    assert.deepEqual(methods,['GET']);
    methods.length=0;
    assert.equal(await visitCount({storage,fetcher:async(u,o)=>{methods.push(o.method);throw Error('offline');}}),null);
    assert.deepEqual(methods,['GET']);
  }
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
