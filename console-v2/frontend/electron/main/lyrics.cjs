'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const defaults={enabled:true,overlay:false,alwaysOnTop:true,autoFind:false,palette:'ice',style:'glass',opacity:90};
function settings(value,base=defaults){
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('歌词设置无效');
 const next={...base};
 for(const [key,v] of Object.entries(value)){
  if(['enabled','overlay','alwaysOnTop','autoFind'].includes(key)&&typeof v==='boolean')next[key]=v;
  else if(key==='palette'&&['ice','white','rose','gold'].includes(v))next[key]=v;
  else if(key==='style'&&['glass','plain','outline'].includes(v))next[key]=v;
  else if(key==='opacity'&&Number.isInteger(v)&&v>=20&&v<=100)next[key]=v;
  else throw Error('歌词设置无效');
 }
 return next;
}
function parseLyrics(text){
 if(typeof text!=='string'||Buffer.byteLength(text)>262144)throw Error('歌词文件不能超过 256 KB');
 text=text.replace(/^\uFEFF/,'').replace(/\r/g,'');
 const offset=Number(text.match(/\[offset:([+-]?\d+)\]/i)?.[1]||0)/1000;
 const lines=[];
 for(const line of text.split('\n')){
  const stamps=[...line.matchAll(/\[(\d{1,3}):([0-5]\d)(?:[.:](\d{1,3}))?\]/g)];
  const body=line.replace(/\[[^\]]*\]/g,'').trim().slice(0,500);
  if(stamps.length)for(const m of stamps)lines.push({at:Math.max(0,Number(m[1])*60+Number(m[2])+Number('0.'+(m[3]||'0'))+offset),text:body});
 }
 if(lines.length){lines.sort((a,b)=>a.at-b.at);return {timed:true,lines:lines.slice(0,3000)};}
 const plain=text.split('\n').filter(s=>!/^\s*\[\w+:.*\]\s*$/.test(s)).map(s=>s.trim()).filter(Boolean).slice(0,3000).map(s=>({at:0,text:s.slice(0,500)}));
 if(!plain.length)throw Error('文件中没有可显示的歌词');
 return {timed:false,lines:plain};
}
function songKey(media){return media?.available&&media.title?crypto.createHash('sha256').update(JSON.stringify([media.app||'',media.title,media.artist||''])).digest('hex'):'';}
function position(media,now=Date.now()){
 const elapsed=media.status==='Playing'&&media.observedAt?Math.max(0,Math.min(10,(now-media.observedAt)/1000))*(media.rate??1):0;
 return Math.max(media.start||0,Math.min(media.duration||0,(media.position||0)+elapsed));
}
class Lyrics {
 constructor({directory,getMedia,fetchImpl=fetch}){
  this.directory=directory;fs.mkdirSync(directory,{recursive:true});this.getMedia=getMedia;this.fetch=fetchImpl;
  this.settings={...defaults};this.key='';this.track=null;this.error='';this.busy=false;this.attempted=new Set();
  try{this.settings=settings(JSON.parse(fs.readFileSync(path.join(directory,'settings.json'),'utf8')));}catch{}
 }
 sync(){
  const key=songKey(this.getMedia());if(key===this.key)return;
  this.key=key;this.track=null;this.error='';
  if(key)try{const cached=JSON.parse(fs.readFileSync(path.join(this.directory,key+'.json'),'utf8'));this.track={...parseLyrics(cached.text),source:cached.source,text:cached.text};}catch{}
 }
 snapshot(){
  this.sync();
  if(this.settings.enabled&&this.settings.autoFind&&this.key&&!this.track&&!this.busy&&!this.attempted.has(this.key)){
   const key=this.key;this.attempted.add(key);
   // Bound per-session bookkeeping; cached songs are stored separately on disk.
   if(this.attempted.size>500)this.attempted.delete(this.attempted.values().next().value);
   queueMicrotask(()=>{if(this.settings.enabled&&this.settings.autoFind&&this.key===key&&!this.busy&&!this.track)void this.find().catch(()=>{});else this.attempted.delete(key);});
  }
  return {settings:this.settings,key:this.key,timed:this.track?.timed||false,lines:this.track?.lines||[],source:this.track?.source||'',busy:this.busy,error:this.error};
 }
 set(value){const next=settings(value,this.settings);fs.writeFileSync(path.join(this.directory,'settings.json'),JSON.stringify(next));this.settings=next;this.changed?.();return this.snapshot();}
 store(text,source,key){
  this.sync();if(!key||key!==this.key)throw Error('曲目已切换，请为当前歌曲重试');
  const parsed=parseLyrics(text);
  fs.writeFileSync(path.join(this.directory,key+'.json'),JSON.stringify({text,source}));
  this.track={...parsed,text,source};this.error='';this.changed?.();
 }
 async run(task){if(this.busy)throw Error('正在获取歌词，请稍候');this.busy=true;this.error='';try{await task();}catch(e){this.error=['AbortError','TimeoutError'].includes(e.name)?'获取歌词超时，可稍后重试或导入本地歌词':e instanceof TypeError?'歌词服务连接失败，可稍后重试或导入本地歌词':e.message;throw Error(this.error);}finally{this.busy=false;this.changed?.();}return this.snapshot();}
 async find(){
  this.sync();const key=this.key,m={...this.getMedia()};if(!key)throw Error('请先在音乐播放器中打开一首歌');
  return this.run(async()=>{
   const query=new URLSearchParams({track_name:m.title,artist_name:m.artist||''});
   if(m.duration>0)query.set('duration',String(Math.round(m.duration-(m.start||0))));
   const response=await this.fetch('https://lrclib.net/api/get?'+query,{signal:AbortSignal.timeout(10000),redirect:'error',headers:{'User-Agent':'Yuki/1.1 (desktop lyrics)'}});
   if(response.status===404)throw Error('未找到匹配歌词，可导入本地 LRC 或 TXT');
   if(!response.ok)throw Error('歌词服务暂不可用，请稍后重试或导入本地歌词');
   // Limit streamed responses rather than trusting Content-Length.
   const reader=response.body.getReader();let size=0;const chunks=[];
   try{while(true){const {done,value}=await reader.read();if(done)break;size+=value.length;if(size>524288)throw Error('歌词服务返回内容过大');chunks.push(Buffer.from(value));}}finally{await reader.cancel().catch(()=>{});}
   const result=JSON.parse(Buffer.concat(chunks).toString('utf8'));
   if(result.instrumental)throw Error('这首曲目被标记为纯音乐');
   if(!result.syncedLyrics&&!result.plainLyrics)throw Error('这首歌暂未提供歌词，可导入本地歌词');
   this.store(result.syncedLyrics||result.plainLyrics,'LRCLIB · 联网匹配',key);
  });
 }
 async importFile(select){
  this.sync();const key=this.key;if(!key)throw Error('请先在音乐播放器中打开一首歌');
  return this.run(async()=>{const file=await select();if(!file)return;if(!['.lrc','.txt'].includes(path.extname(file).toLowerCase()))throw Error('请选择 LRC 或 TXT 文件');if((await fs.promises.stat(file)).size>262144)throw Error('歌词文件不能超过 256 KB');const bytes=await fs.promises.readFile(file);let text;
   if(bytes[0]===255&&bytes[1]===254)text=new TextDecoder('utf-16le').decode(bytes);
   else if(bytes[0]===254&&bytes[1]===255)text=new TextDecoder('utf-16be').decode(bytes);
   else try{text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{text=new TextDecoder('gb18030').decode(bytes);}
   this.store(text,'本地导入 · '+path.basename(file),key);});
 }
}
module.exports={Lyrics,parseLyrics,settings,songKey,position,defaults};
