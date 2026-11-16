'use strict';
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const os=require('node:os');
const {spawn}=require('node:child_process');
const {pinyin}=require('pinyin-pro');

const CLIPBOARD_PREVIEW=240,CLIPBOARD_LIMIT=256000;
class ClipboardHistory {
  constructor(){this.entries=[];this.paused=false;this.last='';}
  capture(text){
    if(typeof text!=='string'||!text.trim())return false;
    const digest=crypto.createHash('sha256').update(text).digest('hex');
    if(this.paused){this.last=digest;return false;}
    if(digest===this.last)return false;
    this.last=digest;
    if(Buffer.byteLength(text)>CLIPBOARD_LIMIT)return false;
    this.entries=[{id:digest,text,preview:text.slice(0,CLIPBOARD_PREVIEW),chars:text.length,truncated:text.length>CLIPBOARD_PREVIEW,at:Date.now()},...this.entries.filter(e=>e.id!==digest)].slice(0,10);
    return true;
  }
  // Snapshots only carry the preview; the body is fetched when the detail pane actually opens.
  payload(){return this.entries.map(({text,...item})=>item);}
  body(id){const entry=this.entries.find(item=>item.id===id);if(!entry)throw new Error('记录已经移除');return entry.text;}
  clear(){this.entries=[];}
}

async function weather(city,fetchImpl=fetch){
  if(typeof city!=='string'||city.trim().length<1||city.length>80)throw new Error('请输入城市名称');
  const get=async url=>{const r=await fetchImpl(url,{signal:AbortSignal.timeout(10000),redirect:'error'});if(!r.ok)throw new Error('天气服务暂不可用，请重试');return r.json();};
  const query=city.trim();
  // Chinese city names are searched first. Some aliases include the administrative suffix
  // “市”, so retry without that suffix when the exact input has no match.
  const searchTerms=[query,...(query.endsWith('市')?[query.slice(0,-1)]:[])];
  let results=[];
  for(const term of searchTerms){
    const geo=await get('https://geocoding-api.open-meteo.com/v1/search?count=10&language=zh&name='+encodeURIComponent(term));
    results=Array.isArray(geo.results)?geo.results:[];
    if(results.length)break;
  }
  // GeoNames does not index every Chinese alias (e.g. “常州”). Transliterate locally
  // and retry the same geocoder; language=zh keeps returned place names Chinese.
  if(!results.length&&/[\u3400-\u9fff]/.test(query)){
    for(const term of searchTerms){
      const romanized=pinyin(term,{toneType:'none',type:'array'}).join('');
      if(!romanized||romanized.toLowerCase()===term.toLowerCase())continue;
      const geo=await get('https://geocoding-api.open-meteo.com/v1/search?count=10&language=zh&name='+encodeURIComponent(romanized));
      results=Array.isArray(geo.results)?geo.results:[];
      if(results.length)break;
    }
  }
  const normalize=value=>String(value||'').trim().replace(/市$/,'');
  const place=results.find(item=>normalize(item.name)===normalize(query))||results[0];
  if(!place)throw new Error('没有找到这个城市，请检查中文名称，或补充省份缩小范围');
  const data=await get(`https://api.open-meteo.com/v1/forecast?latitude=${place.latitude}&longitude=${place.longitude}&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&forecast_days=1&timezone=auto`);
  return {city:place.name,region:place.admin1||place.country,at:Date.now(),...data.current,high:data.daily?.temperature_2m_max?.[0],low:data.daily?.temperature_2m_min?.[0]};
}

class DesktopServices {
  constructor({app,clipboard,powerMonitor,react,fetchImpl=fetch,log=()=>{},spawnImpl=spawn}){
    Object.assign(this,{app,clipboard,powerMonitor,react,fetchImpl,log,spawnImpl});
    this.failures={};this.history=new ClipboardHistory();this.events=[];this.media={available:false};
    this.cpuPrevious=null;this.system={cpu:0,memoryUsed:os.totalmem()-os.freemem(),memoryTotal:os.totalmem()};this.sampleSystem();
    this.battery={available:false};this.drives=[];this.drivesInitialized=false;this.timers=[];this.watchers=[];this.pending=new Map();this.seen=new Map();this.weather=null;this.city='';this.weatherAt=0;this.weatherBusy=null;
    this.inbox=path.join(app.getPath('userData'),'events');fs.mkdirSync(this.inbox,{recursive:true});
    this.settingsPath=path.join(app.getPath('userData'),'desktop.json');
    this.clipboardPath=path.join(app.getPath('userData'),'clipboard-history.json');
    let removeLegacyGuessedCity=false;
    try{const saved=JSON.parse(fs.readFileSync(this.settingsPath,'utf8'));removeLegacyGuessedCity=saved.cityMode==='ip';this.city=removeLegacyGuessedCity?'':String(saved.city||'').slice(0,80);this.history.paused=!!saved.clipboardPaused;}catch(error){if(fs.existsSync(this.settingsPath))this.fail('桌面设置读取',error);}
    if(removeLegacyGuessedCity)this.save();
    this.loadClipboardHistory();
    this.downloads=app.getPath('downloads');
    try{for(const name of fs.readdirSync(this.downloads)){const stat=fs.statSync(path.join(this.downloads,name));this.seen.set(name,`${stat.size}:${stat.mtimeMs}`);}}catch(error){this.fail('下载目录首扫',error);}
    // Do not replay notifications left by a previous session.
    try{for(const name of fs.readdirSync(this.inbox))this.inboxSeen=(this.inboxSeen||new Set()).add(name);}catch(error){this.fail('收件箱首扫',error);}
    this.inboxSeen ||= new Set();
  }
  // Failures used to vanish into empty catch blocks. Counting them keeps the log readable
  // while still showing how often the same collector trips.
  fail(label,error){
    const item=this.failures[label]||{count:0,last:''};item.count++;item.last=String(error?.message||error);this.failures[label]=item;
    if(item.count===1||item.count%100===0)this.log(`桌面采集失败（${label}，累计 ${item.count} 次）：${item.last}`);
  }
  changed(){try{this.onChanged?.();}catch(error){this.fail('快照通知',error);}}
  save(){try{fs.writeFileSync(this.settingsPath,JSON.stringify({city:this.city,clipboardPaused:this.history.paused}));}catch(error){this.fail('桌面设置写入',error);}}
  loadClipboardHistory(){
    try{
      const saved=JSON.parse(fs.readFileSync(this.clipboardPath,'utf8'));
      if(!Array.isArray(saved))throw new Error('剪贴板历史格式无效');
      this.history.entries=saved.filter(item=>item&&typeof item.text==='string'&&item.text.trim()&&Buffer.byteLength(item.text)<=CLIPBOARD_LIMIT&&Number.isFinite(item.at))
        .map(item=>({id:crypto.createHash('sha256').update(item.text).digest('hex'),text:item.text,preview:item.text.slice(0,CLIPBOARD_PREVIEW),chars:item.text.length,truncated:item.text.length>CLIPBOARD_PREVIEW,at:item.at}))
        .filter((item,index,items)=>items.findIndex(other=>other.id===item.id)===index).slice(0,10);
    }catch(error){if(error.code!=='ENOENT')this.fail('剪贴板历史读取',error);}
  }
  saveClipboardHistory(){
    const temporary=this.clipboardPath+'.tmp';
    try{fs.writeFileSync(temporary,JSON.stringify(this.history.entries));fs.renameSync(temporary,this.clipboardPath);}
    catch(error){try{fs.rmSync(temporary,{force:true});}catch{}this.fail('剪贴板历史写入',error);}
  }
  event(kind,text){
    if(!['usb','charging','download','success','failure','thinking','working','waiting','done','error'].includes(kind))return;
    const last=this.events[0];if(last&&last.kind===kind&&last.text===text&&Date.now()-last.at<10000)return;
    const entry={kind,text:String(text).slice(0,180),at:Date.now()};this.events=[entry,...this.events].slice(0,20);
    Promise.resolve(this.react(entry)).catch(error=>this.fail('事件转发',error));
    this.changed();
  }
  // The fallback cadence lives here so it can be asserted without arming real timers.
  pollerSpecs(){return [['系统采样',3000,()=>this.sampleSystem()],['剪贴板',2000,()=>this.readClipboard()],['下载目录兜底',20000,()=>this.scanDownloads()],['收件箱兜底',20000,()=>this.scanInbox()]];}
  start(){
    if(this.started)return;this.started=true;
    // Slow fallbacks only: the clipboard and the two folders now report changes through
    // signals, so an idle desktop costs one hash comparison every two seconds.
    this.pollers=this.pollerSpecs();
    // Observe changes after launch; never ingest the pre-existing clipboard.
    void this.readClipboardBaseline();
    this.arm();this.watch();
    this.onAC=()=>this.event('charging','接上电源了。');this.powerMonitor.on('on-ac',this.onAC);
    this.rest=()=>{this.disarm();for(const watcher of this.watchers)watcher.close();this.watchers=[];};
    this.wake=()=>{
      if(!this.started)return;this.arm();this.watch();
      try{this.scanDownloads();this.scanInbox();}catch(error){this.fail('唤醒扫描',error);}
      void this.readClipboard().catch(error=>this.fail('剪贴板',error));
    };
    for(const [name,handler] of [['lock-screen',this.rest],['suspend',this.rest],['unlock-screen',this.wake],['resume',this.wake]])this.powerMonitor.on(name,handler);
    if(process.platform==='win32'){
      this.worker=this.spawnImpl('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(__dirname,'windows-status.ps1')],{windowsHide:true,stdio:['ignore','pipe','pipe']});
      let buffer='';this.worker.stdout.setEncoding('utf8');this.worker.stdout.on('data',chunk=>{
        buffer+=chunk;if(buffer.length>65536){buffer='';this.fail('电源监听输出',Error('状态行超长，已丢弃缓冲'));return;}
        const lines=buffer.split('\n');buffer=lines.pop();for(const line of lines){
          let value=null;try{value=JSON.parse(line);}catch(error){this.fail('电源监听解析',error);continue;}
          const before=JSON.stringify([this.battery,this.drives]);
          this.battery=value.battery;
          if(this.drivesInitialized){for(const drive of value.drives||[])if(!this.drives.includes(drive))this.event('usb',`发现新的 U 盘：${drive}`);}
          this.drives=value.drives||[];this.drivesInitialized=true;
          if(before!==JSON.stringify([this.battery,this.drives]))this.changed();
        }
      });
      this.worker.stderr.resume();this.worker.on('error',error=>this.fail('电源监听进程',error));
    }
  }
  arm(){
    if(this.timers.length||!this.started)return;
    for(const [label,ms,fn] of this.pollers){
      let busy=false;
      this.timers.push(setInterval(async()=>{
        if(busy||!this.started)return;busy=true;
        try{await fn();}catch(error){this.fail(label,error);}finally{busy=false;}
      },ms));
    }
  }
  disarm(){for(const timer of this.timers)clearInterval(timer);this.timers=[];}
  watch(){
    if(this.watchers.length)return;
    for(const [directory,label] of [[this.downloads,'下载目录'],[this.inbox,'收件箱']]){
      let watcher=null;
      try{watcher=fs.watch(directory,()=>this.queueScan());}catch(error){this.fail(label+'监听',error);continue;}
      watcher.on('error',error=>{this.fail(label+'监听',error);watcher.close();this.watchers=this.watchers.filter(item=>item!==watcher);});
      this.watchers.push(watcher);
    }
  }
  queueScan(){if(this.scanQueued)return;this.scanQueued=setTimeout(()=>{this.scanQueued=null;this.scanDownloads();this.scanInbox();},250);}
  readClipboardBaseline(){
    return this.clipboard.readText().then(text=>{this.history.last=crypto.createHash('sha256').update(text).digest('hex');this.baseline=true;}).catch(error=>{this.baseline=true;this.fail('剪贴板基线',error);});
  }
  async readClipboard(){
    if(!this.baseline||Date.now()<(this.clipboardSuppressedUntil||0))return;
    if(this.history.capture(await this.clipboard.readText())){this.saveClipboardHistory();this.changed();}
  }
  scanDownloads(){
    const now=Date.now();let names;try{names=fs.readdirSync(this.downloads);}catch(error){this.fail('下载目录扫描',error);return;}
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
      try{
        const file=path.join(this.inbox,name);
        if(fs.statSync(file).size>4096){this.inboxSeen.add(name);continue;}
        const value=JSON.parse(fs.readFileSync(file,'utf8'));
        if(['success','failure','download','thinking','working','waiting','done','error'].includes(value.kind)&&typeof value.text==='string')this.event(value.kind,value.text);
        fs.unlinkSync(file);
      }catch(error){this.inboxSeen.add(name);this.fail('收件箱读取',error);}
    }
  }
  sampleSystem(){
    const next=os.cpus().reduce((a,c)=>({idle:a.idle+c.times.idle,total:a.total+Object.values(c.times).reduce((x,y)=>x+y,0)}),{idle:0,total:0});
    const p=this.cpuPrevious,total=p?next.total-p.total:0;
    const cpu=total>0?Math.max(0,Math.min(100,100*(1-(next.idle-p.idle)/total))):0,memoryUsed=os.totalmem()-os.freemem();
    // Rounding is deliberate: a nudge of one percent is noise, and pushing it would wake the
    // renderer every three seconds for nothing.
    const moved=Math.abs(cpu-this.system.cpu)>=2||Math.abs(memoryUsed-this.system.memoryUsed)>=33554432;
    this.system={cpu,memoryUsed,memoryTotal:os.totalmem()};this.cpuPrevious=next;
    if(moved)this.changed();
  }
  snapshot(){
    let autostart;
    try{autostart=!!this.app.getLoginItemSettings?.().openAtLogin;}catch(error){this.fail('开机自启读取',error);}
    return {clipboard:this.history.payload(),clipboardPaused:this.history.paused,media:this.media,battery:this.battery,drives:this.drives,events:this.events,weather:this.weather,city:this.city,inbox:this.inbox,system:this.system,autostart};
  }
  clipboardBody(id){
    if(typeof id!=='string'||!/^[a-f0-9]{64}$/.test(id))throw new Error('记录编号无效');
    return this.history.body(id);
  }
  async loadWeather(city){
    const name=typeof city==='string'?city.trim():'';
    if(!name||name.length>80)throw new Error('请输入城市名称');
    // Ten minutes of grace keeps the periodic snapshot from hammering the weather service.
    if(name===this.city&&this.weather&&Date.now()-this.weatherAt<=600000){this.save();this.changed();return;}
    if(this.weatherBusy)throw new Error('正在获取天气，请稍候');
    this.weatherBusy=weather(name,this.fetchImpl);
    try{const result=await this.weatherBusy;this.weather=result;this.weatherAt=Date.now();this.city=result.city||name;this.save();this.changed();}finally{this.weatherBusy=null;}
  }
  async action(input){
    if(!input||typeof input!=='object'||Array.isArray(input)||JSON.stringify(input).length>1024)throw new Error('桌面工具参数无效');
    const {name,value}=input;
    if(name==='snapshot')return this.snapshot();
    if(name==='notify'){if(typeof value!=='string'||value.length>600)throw new Error('提醒内容无效');this.notify?.(value);}
    else if(name==='autostart'){if(typeof value!=='boolean')throw new Error('开关值无效');const options={openAtLogin:value,path:process.execPath};if(!this.app.isPackaged)options.args=[path.resolve(__dirname,'index.cjs')];this.app.setLoginItemSettings(options);if(!!this.app.getLoginItemSettings().openAtLogin!==value)throw new Error('系统未能更新开机自启，请检查权限');}
    else if(name==='clipboard-delete'){if(typeof value!=='string')throw new Error('记录编号无效');this.history.entries=this.history.entries.filter(e=>e.id!==value);this.saveClipboardHistory();}
    else if(name==='clipboard-pause'){if(typeof value!=='boolean')throw new Error('开关值无效');this.history.paused=value;this.save();}
    else if(name==='clipboard-clear'){this.history.clear();this.saveClipboardHistory();}
    else if(name==='clipboard-copy'){const entry=this.history.entries.find(e=>e.id===value);if(!entry)throw new Error('记录已经移除');await this.clipboard.writeText(entry.text);this.history.last=entry.id;}
    else if(name==='weather')await this.loadWeather(value);
    else throw new Error('未知桌面工具');
    return this.snapshot();
  }
  stop(){
    this.started=false;this.disarm();
    for(const watcher of this.watchers)watcher.close();this.watchers=[];
    if(this.scanQueued){clearTimeout(this.scanQueued);this.scanQueued=null;}
    this.worker?.kill();
    const monitor=[['on-ac',this.onAC],['lock-screen',this.rest],['suspend',this.rest],['unlock-screen',this.wake],['resume',this.wake]];
    for(const [name,handler] of monitor)if(handler)this.powerMonitor.removeListener(name,handler);
  }
}
module.exports={ClipboardHistory,DesktopServices,weather};
