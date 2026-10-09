import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { initDhaak } from '../site/dhaak.mjs';
function fixture(bn=false) {
  const listeners={};
  const target=()=>({attributes:{},listeners:{},addEventListener(k,fn){this.listeners[k]=fn;},setAttribute(k,v){this.attributes[k]=v;},getAttribute(k){return this.attributes[k];}});
  const button=target(),audio=target(),label={},message={}; let plays=0;
  Object.assign(audio,{currentTime:0,paused:true,play(){plays++;this.paused=false;return Promise.resolve();},pause(){this.paused=true;}});
  const nodes={'dhaak-toggle':button,'dhaak-audio':audio,'dhaak-label':label,'dhaak-status':message};
  const doc={documentElement:{lang:bn?'bn':'en'},visibilityState:'visible',body:{classList:{contains:()=>true}},getElementById:id=>nodes[id],addEventListener(k,fn){listeners[k]=fn;}};
  const win={location:{search:''},addEventListener(k,fn){listeners[k]=fn;}};
  initDhaak({doc,win});
  return {button,audio,label,message,doc,win,listeners,plays:()=>plays,click:()=>button.listeners.click()};
}
test('no autoplay/source assignment/preference on initialization; native accessible button',()=>{
  const f=fixture(); assert.equal(f.plays(),0); assert.equal(f.audio.getAttribute('src'),undefined);
  assert.equal(f.audio.preload,'none'); assert.equal(f.audio.volume,0.22); assert.equal(f.button.attributes['aria-pressed'],'false');
  const html=readFileSync('site/index.html','utf8');
  assert.match(html,/<button id="dhaak-toggle"[^>]*type="button"/);
  assert.match(html,/<audio id="dhaak-audio" preload="none"><\/audio>/);
});
test('explicit play loops, second click stops and resets',async()=>{
  const f=fixture(); await f.click(); assert.equal(f.plays(),1); assert.equal(f.audio.loop,true);
  assert.equal(f.audio.getAttribute('src'),'assets/puja/dhaak.mp3'); assert.equal(f.label.textContent,'Stop dhaak');
  f.audio.currentTime=12; await f.click(); assert.equal(f.audio.paused,true); assert.equal(f.audio.currentTime,0);
  assert.equal(f.audio.loop,false); assert.equal(f.button.attributes['aria-pressed'],'false');
});
test('play rejection and missing recording fail quietly and reset UI',async()=>{
  const f=fixture(); f.audio.play=()=>Promise.reject(Error('unavailable')); await f.click();
  assert.match(f.message.textContent,/unavailable/); assert.equal(f.audio.loop,false);
  f.audio.listeners.error(); assert.equal(f.label.textContent,'Hear the dhaak');
});
test('ended resets, fresh page never resumes',async()=>{
  const f=fixture(); await f.click(); f.audio.listeners.ended();
  assert.equal(f.audio.currentTime,0); assert.equal(f.audio.loop,false); assert.equal(f.label.textContent,'Hear the dhaak');
  assert.equal(fixture().plays(),0);
});
test('hidden page, pagehide, safety/history and document links stop audio',async()=>{
  for(const action of ['hidden','pagehide','safety','link']) {
    const f=fixture(); await f.click(); f.audio.currentTime=4;
    if(action==='hidden'){f.doc.visibilityState='hidden';f.listeners.visibilitychange();}
    if(action==='pagehide')f.listeners.pagehide();
    if(action==='safety'){f.win.location.search='?module=safety';f.listeners.popstate();}
    if(action==='link')f.listeners.click({target:{closest:()=>({})}});
    assert.equal(f.audio.paused,true); assert.equal(f.audio.currentTime,0); assert.equal(f.audio.loop,false);
  }
});
test('inappropriate context cannot start audio; Bengali labels reflect state',async()=>{
  const f=fixture(true); assert.equal(f.label.textContent,'ঢাক শুনুন'); await f.click(); assert.equal(f.label.textContent,'ঢাক থামান');
  await f.click(); f.doc.body.classList.contains=()=>false; await f.click(); assert.equal(f.plays(),1);
});
test('stop while play promise pending cannot leave looping enabled',async()=>{
  const f=fixture(); let resolve; f.audio.play=()=>new Promise(r=>resolve=r);
  const pending=f.click(); await f.click(); resolve(); await pending;
  assert.equal(f.audio.paused,true); assert.equal(f.audio.loop,false); assert.equal(f.button.attributes['aria-pressed'],'false');
});
test('an older play promise cannot stop a newer explicit playback request',async()=>{
  const f=fixture(); let resolve; f.audio.play=()=>new Promise(r=>resolve=r);
  const old=f.click(); await f.click();
  f.audio.play=()=>{f.audio.paused=false;return Promise.resolve();}; await f.click();
  resolve(); await old; assert.equal(f.audio.loop,true); assert.equal(f.button.attributes['aria-pressed'],'true');
});
test('supplied recording remains byte-for-byte unchanged with documented provenance',()=>{
  const hash=createHash('sha256').update(readFileSync('site/assets/puja/dhaak.mp3')).digest('hex');
  assert.equal(hash,'3739d5a86272f64058a9bd146df345e3fb1ad6f5ecfb8b138c382e8394f5dfa0');
  assert.ok(readFileSync('docs/assets/ASSET_PROVENANCE.md','utf8').includes(hash));
});
