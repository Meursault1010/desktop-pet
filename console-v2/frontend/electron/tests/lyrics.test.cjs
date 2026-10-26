const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {Lyrics,parseLyrics,settings,position}=require('../main/lyrics.cjs');
function fixture(t,fetchImpl){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-lyrics-'));t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));
 const media={available:true,app:'player',title:'Song',artist:'Artist',duration:240};
 const service=new Lyrics({directory,getMedia:()=>media,fetchImpl});return {service,media,directory};
}
test('LRC handles multiple timestamps, offset, blank breaks and text-only lyrics',()=>{
 const l=parseLyrics('[ar:歌手]\n[offset:-500]\n[00:02.50][01:00.123]第二句\n[00:01]第一句\n[00:03]\n');
 assert.equal(l.timed,true);assert.deepEqual(l.lines,[{at:.5,text:'第一句'},{at:2,text:'第二句'},{at:2.5,text:''},{at:59.623,text:'第二句'}]);
 assert.deepEqual(parseLyrics('第一句\n第二句').lines,[{at:0,text:'第一句'},{at:0,text:'第二句'}]);
 assert.throws(()=>parseLyrics('[ar:Artist]'),/没有/);assert.throws(()=>parseLyrics('a'.repeat(262145)),/256/);
});
test('settings validate bounds and survive restart; cached lyrics follow track identity',t=>{
 const {service,media,directory}=fixture(t);service.snapshot();service.store('[00:00]local','本地',service.key);
 service.set({opacity:55,palette:'rose',overlay:true,alwaysOnTop:false,style:'outline'});
 const restarted=new Lyrics({directory,getMedia:()=>media});assert.equal(restarted.snapshot().lines[0].text,'local');assert.equal(restarted.settings.opacity,55);
 media.title='Other';assert.equal(service.snapshot().lines.length,0);media.title='Song';assert.equal(service.snapshot().lines[0].text,'local');
 for(const v of [{opacity:0},{opacity:101},{opacity:NaN},{overlay:'yes'},{palette:'red'},{path:'x'},[]])assert.throws(()=>settings(v),/无效/);
});
test('online lyrics sends only song metadata and caches exact returned lyrics',async t=>{
 let called;
 const {service}=fixture(t,async(url,options)=>{called={url,options};return new Response(JSON.stringify({syncedLyrics:'[00:01]actual',plainLyrics:'unused'}));});
 const result=await service.find();assert.equal(result.lines[0].text,'actual');assert.equal(result.timed,true);
 const u=new URL(called.url);assert.equal(u.origin,'https://lrclib.net');assert.equal(u.searchParams.get('track_name'),'Song');assert.equal(u.searchParams.get('artist_name'),'Artist');assert.equal(u.searchParams.get('duration'),'240');assert.ok(called.options.signal);assert.equal(called.options.redirect,'error');
});
test('missing lyrics and stale async results never masquerade as current song lyrics',async t=>{
 const {service,media}=fixture(t,async()=>new Response('',{status:404}));
 await assert.rejects(service.find(),/未找到/);assert.equal(service.snapshot().lines.length,0);assert.equal(service.busy,false);
 let finish;service.fetch=()=>new Promise(resolve=>{finish=resolve;});
 const pending=service.find();await assert.rejects(service.find(),/稍候/);media.title='New';service.snapshot();
 finish(new Response(JSON.stringify({plainLyrics:'old song'})));await assert.rejects(pending,/切换/);assert.equal(service.snapshot().lines.length,0);
});
test('local import accepts bounded lyric files and refuses a changed song',async t=>{
 const {service,media,directory}=fixture(t);const file=path.join(directory,'test.lrc');fs.writeFileSync(file,'[00:00]本地歌词');
 assert.equal((await service.importFile(async()=>file)).lines[0].text,'本地歌词');
 await assert.rejects(service.importFile(async()=>{media.title='Changed';return file;}),/切换/);
 assert.equal(service.snapshot().lines.length,0);
});
test('playback extrapolation respects pause, rate, end and stale-sample cap',()=>{
 const m={status:'Playing',position:10,duration:30,observedAt:1000,rate:2};assert.equal(position(m,2000),12);assert.equal(position({...m,status:'Paused'},2000),10);assert.equal(position(m,100000),30);
});
test('automatic lookup is opt-in, attempts once per song and follows track changes',async t=>{
 let calls=0;
 const {service,media}=fixture(t,async()=>{calls++;return new Response('',{status:404});});
 service.snapshot();await new Promise(r=>setImmediate(r));assert.equal(calls,0);
 service.set({autoFind:true});await new Promise(r=>setImmediate(r));assert.equal(calls,1);
 service.snapshot();service.snapshot();await new Promise(r=>setImmediate(r));assert.equal(calls,1);
 media.title='Second';service.snapshot();await new Promise(r=>setImmediate(r));assert.equal(calls,2);
 service.set({autoFind:false});media.title='Third';service.snapshot();await new Promise(r=>setImmediate(r));assert.equal(calls,2);
});
