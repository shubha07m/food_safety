import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { initDhaak } from '../site/dhaak.mjs';
function fixture(bn=false, reduced=false) {
  const listeners={};
  const target=()=>({attributes:{},listeners:{},addEventListener(k,fn){this.listeners[k]=fn;},setAttribute(k,v){this.attributes[k]=v;},getAttribute(k){return this.attributes[k];}});
  const button=target(),audio=target(),video=target(),label={},message={}; let plays=0;
  Object.assign(video,{style:{},currentTime:0,paused:true,play(){this.paused=false;return Promise.resolve();},pause(){this.paused=true;}});
  Object.assign(audio,{currentTime:0,paused:true,play(){plays++;this.paused=false;return Promise.resolve();},pause(){this.paused=true;}});
  const nodes={'dhaak-toggle':button,'dhaak-audio':audio,'dhaak-video':video,'dhaak-label':label,'dhaak-status':message};
  const doc={documentElement:{lang:bn?'bn':'en'},visibilityState:'visible',body:{classList:{contains:()=>true}},getElementById:id=>nodes[id],addEventListener(k,fn){listeners[k]=fn;}};
  const motion={matches:reduced,addEventListener(k,fn){this.changed=fn;}};
  const win={location:{search:''},matchMedia:()=>motion,addEventListener(k,fn){listeners[k]=fn;}};
  initDhaak({doc,win});
  return {button,audio,video,motion,label,message,doc,win,listeners,plays:()=>plays,click:()=>button.listeners.click()};
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
    assert.equal(f.video.paused,true); assert.equal(f.video.currentTime,0); assert.equal(f.video.loop,false); assert.equal(f.video.style.visibility,'hidden');
  }
});
test('video loads only after explicit audio play, always muted with no media controls',async()=>{
  const f=fixture(); assert.equal(f.video.getAttribute('src'),undefined); assert.equal(f.video.paused,true);
  assert.equal(f.video.muted,true); assert.equal(f.video.volume,0); assert.equal(f.video.preload,'none');
  await f.click(); assert.equal(f.video.getAttribute('src'),'assets/puja/dhaak-playing.mp4');
  assert.equal(f.video.loop,true); assert.equal(f.video.style.visibility,'visible');
  f.video.muted=false; f.video.volume=1; f.video.listeners.volumechange();
  assert.equal(f.video.muted,true); assert.equal(f.video.volume,0);
  f.video.currentTime=3; await f.click(); assert.equal(f.video.currentTime,0); assert.equal(f.video.paused,true);
  const tag=readFileSync('site/index.html','utf8').match(/<video id="dhaak-video"[^>]*>/)[0];
  assert.match(tag,/muted playsinline preload="none"/); assert.match(tag,/aria-hidden="true"/);
  assert.doesNotMatch(tag,/autoplay|controls|src=/);
});
test('reduced motion keeps video unloaded and sound independent',async()=>{
  const f=fixture(false,true); await f.click(); assert.equal(f.audio.paused,false);
  assert.equal(f.video.getAttribute('src'),undefined); assert.equal(f.video.paused,true);
  f.motion.matches=false; await f.motion.changed(); await Promise.resolve(); assert.equal(f.video.paused,false);
  f.motion.matches=true; f.motion.changed(); assert.equal(f.video.paused,true); assert.equal(f.audio.paused,false);
});
test('video rejection or missing asset never stops sound or leaves visible failed decoration',async()=>{
  const f=fixture(); f.video.play=()=>Promise.reject(Error('missing')); await f.click();
  assert.equal(f.audio.paused,false); assert.equal(f.video.style.visibility,'hidden');
  f.video.listeners.error(); assert.equal(f.audio.paused,false);
});
test('failed audio never starts video, and ended audio resets both',async()=>{
  const f=fixture(); f.audio.play=()=>Promise.reject(Error('blocked')); await f.click();
  assert.equal(f.video.getAttribute('src'),undefined);
  const g=fixture(); await g.click(); g.video.currentTime=4; g.audio.listeners.ended();
  assert.equal(g.video.currentTime,0); assert.equal(g.video.loop,false); assert.equal(g.video.style.visibility,'hidden');
});
test('late video promise cannot restore decoration after stop',async()=>{
  const f=fixture(); let resolve; f.video.play=()=>new Promise(r=>resolve=r);
  const playing=f.click(); await Promise.resolve(); await f.click(); resolve(); await playing;
  assert.equal(f.video.style.visibility,'hidden'); assert.equal(f.video.loop,false);
});
test('supplied video is unchanged and provenance records its checksum',()=>{
  const hash=createHash('sha256').update(readFileSync('site/assets/puja/dhaak-playing.mp4')).digest('hex');
  assert.equal(hash,'2ddce497a3fa9a0a704173e9e06008a307ab4355dbfaf43ecb863147216785cb');
  assert.ok(readFileSync('docs/assets/ASSET_PROVENANCE.md','utf8').includes(hash));
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
