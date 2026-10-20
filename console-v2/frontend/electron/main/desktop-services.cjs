'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const {spawn}=require('node:child_process');

class ClipboardHistory {
  constructor(){this.entries=[];this.paused=false;this.last='';}
  capture(text){
    if(typeof text!=='string'||!text.trim())return;
    const digest=crypto.createHash('sha256').update(text).digest('hex');
    if(this.paused){this.last=digest;return;}
    if(digest===this.last)return;
    this.last=digest;
    if(Buffer.byteLength(text)>256000)return;
    this.entries=[{id:digest,text,at:Date.now()},...this.entries.filter(e=>e.id!==digest)].slice(0,10);
  }
  clear(){this.entries=[];}
}

async function weather(city,fetchImpl=fetch){
  if(typeof city!=='string'||city.trim().length<1||city.length>80)throw new Error('请输入城市名称');
  const get=async url=>{const r=await fetchImpl(url,{signal:AbortSignal.timeout(10000),redirect:'error'});if(!r.ok)throw new Error('天气服务暂不可用，请重试');return r.json();};
  const geo=await get('https://geocoding-api.open-meteo.com/v1/search?count=1&language=zh&name='+encodeURIComponent(city.trim()));
  const place=geo.results?.[0];if(!place)throw new Error('没有找到这座城市，请尝试拼音或英文名称');
  const data=await get(`https://api.open-meteo.com/v1/forecast?latitude=${place.latitude}&longitude=${place.longitude}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=auto`);
  return {city:place.name,region:place.admin1||place.country,at:Date.now(),...data.current,high:data.daily?.temperature_2m_max?.[0],low:data.daily?.temperature_2m_min?.[0]};
}

class DesktopServices {
  constructor({app,clipboard,powerMonitor,react,fetchImpl=fetch}){
    Object.assign(this,{app,clipboard,powerMonitor,react,fetchImpl});
    this.history=new ClipboardHistory();this.events=[];this.media={available:false,status:'未检测到播放会话'};
    this.battery={available:false};this.drives=[];this.drivesInitialized=false;this.timers=[];this.pending=new Map();this.seen=new Map();this.weather=null;this.city='';this.weatherAt=0;this.weatherBusy=null;
    this.inbox=path.join(app.getPath('userData'),'events');fs.mkdirSync(this.inbox,{recursive:true});
    this.settingsPath=path.join(app.getPath('userData'),'desktop.json');
    try{const saved=JSON.parse(fs.readFileSync(this.settingsPath,'utf8'));this.city=String(saved.city||'').slice(0,80);this.history.paused=!!saved.clipboardPaused;}catch{}
    this.downloads=app.getPath('downloads');
    try{for(const name of fs.readdirSync(this.downloads)){const stat=fs.statSync(path.join(this.downloads,name));this.seen.set(name,`${stat.size}:${stat.mtimeMs}`);}}catch{}
    // Do not replay notifications left by a previous session.
    try{for(const name of fs.readdirSync(this.inbox))this.inboxSeen=(this.inboxSeen||new Set()).add(name);}catch{}
    this.inboxSeen ||= new Set();
  }
  save(){fs.writeFileSync(this.settingsPath,JSON.stringify({city:this.city,clipboardPaused:this.history.paused}));}
  event(kind,text){
    if(!['usb','charging','download','success','failure'].includes(kind))return;
    const last=this.events[0];if(last&&last.kind===kind&&last.text===text&&Date.now()-last.at<10000)return;
    const entry={kind,text:String(text).slice(0,180),at:Date.now()};this.events=[entry,...this.events].slice(0,20);
    Promise.resolve(this.react(entry)).catch(()=>{});
  }
  start(){
    if(this.started)return;this.started=true;
    const every=(ms,fn)=>{let busy=false;this.timers.push(setInterval(async()=>{if(busy)return;busy=true;try{await fn();}catch{}finally{busy=false;}},ms));};
    // Observe changes after launch; never ingest the pre-existing clipboard.
    let baselineReady=false;
    this.clipboardBaseline=Promise.resolve().then(()=>this.clipboard.readText()).then(text=>{this.history.last=crypto.createHash('sha256').update(text).digest('hex');baselineReady=true;}).catch(()=>{baselineReady=true;});
    every(800,async()=>{if(baselineReady)this.history.capture(await this.clipboard.readText());});
    every(1500,()=>this.scanDownloads());every(1500,()=>this.scanInbox());
    this.onAC=()=>this.event('charging','接上电源了。');this.powerMonitor.on('on-ac',this.onAC);
    if(process.platform==='win32'){
      this.worker=spawn('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(__dirname,'windows-status.ps1')],{windowsHide:true,stdio:['ignore','pipe','pipe']});
      let buffer='';this.worker.stdout.setEncoding('utf8');this.worker.stdout.on('data',chunk=>{
        buffer+=chunk;if(buffer.length>65536){buffer='';return;}
        const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines){try{const value=JSON.parse(line);this.media=value.media;this.battery=value.battery;if(this.drivesInitialized){for(const drive of value.drives||[])if(!this.drives.includes(drive))this.event('usb',`发现新的 U 盘：${drive}`);}this.drives=value.drives||[];this.drivesInitialized=true;}catch{}}
      });
      this.worker.stderr.resume();this.worker.on('error',()=>{this.media={available:false,status:'Windows 媒体服务不可用'};});
      this.worker.on('exit',()=>{this.media={available:false,status:'Windows 媒体服务已停止'};});
    }
  }
  scanDownloads(){
    const now=Date.now();let names;try{names=fs.readdirSync(this.downloads);}catch{return;}
    for(const name of names){
      if(/\.(crdownload|part|partial|tmp|download)$/i.test(name))continue;
      const file=path.join(this.downloads,name);let stat;try{stat=fs.statSync(file);}catch{continue;}
      if(!stat.isFile())continue;
      const fingerprint=`${stat.size}:${stat.mtimeMs}`;
      if(this.seen.get(name)===fingerprint)continue;
      const prior=this.pending.get(name);
      if(prior&&prior.size===stat.size&&prior.mtime===stat.mtimeMs&&now-prior.since>=4500){
        this.seen.set(name,fingerprint);this.pending.delete(name);this.event('download',`下载目录已就绪：${name}`);
      }else if(!prior||prior.size!==stat.size||prior.mtime!==stat.mtimeMs){this.pending.set(name,{size:stat.size,mtime:stat.mtimeMs,since:now});}
    }
    for(const name of this.pending.keys())if(!names.includes(name))this.pending.delete(name);
    for(const name of this.seen.keys())if(!names.includes(name))this.seen.delete(name);
  }
  scanInbox(){
    for(const name of fs.readdirSync(this.inbox)){
      if(!/^[a-zA-Z0-9-]+\.json$/.test(name)||this.inboxSeen.has(name))continue;
      try{const file=path.join(this.inbox,name);if(fs.statSync(file).size>4096){this.inboxSeen.add(name);continue;}const value=JSON.parse(fs.readFileSync(file,'utf8'));if(['success','failure','download'].includes(value.kind)&&typeof value.text==='string')this.event(value.kind,value.text);fs.unlinkSync(file);}catch{}
    }
  }
  snapshot(){return {clipboard:this.history.entries,clipboardPaused:this.history.paused,media:this.media,battery:this.battery,drives:this.drives,events:this.events,weather:this.weather,city:this.city,inbox:this.inbox};}
  async action(input){
    if(!input||typeof input!=='object'||Array.isArray(input)||JSON.stringify(input).length>1024)throw new Error('桌面工具参数无效');
    const {name,value}=input;
    if(name==='snapshot')return this.snapshot();
    if(name==='clipboard-pause'){if(typeof value!=='boolean')throw new Error('开关值无效');this.history.paused=value;this.save();}
    else if(name==='clipboard-clear')this.history.clear();
    else if(name==='clipboard-copy'){const entry=this.history.entries.find(e=>e.id===value);if(!entry)throw new Error('记录已经移除');await this.clipboard.writeText(entry.text);this.history.last=entry.id;}
    else if(name==='weather'){
      if(typeof value!=='string'||value.length>80)throw new Error('城市无效');
      if(value!==this.city||Date.now()-this.weatherAt>600000||!this.weather){
        if(this.weatherBusy)throw new Error('正在获取天气，请稍候');
        this.weatherBusy=weather(value,this.fetchImpl);
        try{const result=await this.weatherBusy;this.weather=result;this.weatherAt=Date.now();this.city=value;this.save();}finally{this.weatherBusy=null;}
      }
    }else throw new Error('未知桌面工具');
    return this.snapshot();
  }
  stop(){for(const timer of this.timers)clearInterval(timer);this.timers=[];this.worker?.kill();if(this.onAC)this.powerMonitor.removeListener('on-ac',this.onAC);this.started=false;}
}
module.exports={ClipboardHistory,DesktopServices,weather};
