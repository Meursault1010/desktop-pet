const {test,mock}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {EventEmitter}=require('node:events');
const {spawnSync}=require('node:child_process');
const {ClipboardHistory,DesktopServices,weather}=require('../main/desktop-services.cjs');
const {ModelConfig,endpoint}=require('../main/model-config.cjs');

function fixture(t){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-desktop-'));
  const downloads=path.join(root,'downloads');fs.mkdirSync(downloads);
  const events=[],logs=[];let copied='original';
  const app={getPath:name=>name==='downloads'?downloads:root};
  const powerMonitor=new EventEmitter();
  // start() is exercised in these tests, so the PowerShell worker stays a stub.
  const worker={stdout:{setEncoding(){},on(){},resume(){}},stderr:{resume(){}},on(){},kill(){}};
  const service=new DesktopServices({app,powerMonitor,clipboard:{readText:async()=>copied,writeText:async value=>{copied=value;}},react:e=>events.push(e),log:m=>logs.push(m),spawnImpl:()=>worker});
  t.after(()=>{service.stop();fs.rmSync(root,{recursive:true,force:true});});
  return {root,downloads,events,logs,service,powerMonitor,read:()=>copied,write:value=>{copied=value;}};
}

test('clipboard keeps ten recent unique texts, pause and clear do not leak old content',()=>{
  const history=new ClipboardHistory();
  for(let i=0;i<12;i++)history.capture('内容 '+i);
  assert.equal(history.entries.length,10);assert.equal(history.entries[0].text,'内容 11');
  history.capture('内容 7');assert.equal(history.entries[0].text,'内容 7');
  history.paused=true;history.capture('private');history.paused=false;history.capture('private');
  assert.ok(history.entries.every(e=>e.text!=='private'));
  history.clear();history.capture('private');assert.equal(history.entries.length,0);
  history.capture('new');assert.equal(history.entries.length,1);
  history.capture('x'.repeat(256001));assert.equal(history.entries.length,1);
});
test('async clipboard copy, settings persistence, drive snapshot and invalid actions',async t=>{
  const {service,read}=fixture(t);service.history.capture('中文剪切板');
  const result=await service.action({name:'clipboard-copy',value:service.history.entries[0].id});
  assert.equal(read(),'中文剪切板');assert.equal(result.drives.length,0);
  await service.action({name:'clipboard-pause',value:true});
  assert.equal(JSON.parse(fs.readFileSync(service.settingsPath,'utf8')).clipboardPaused,true);
  await service.action({name:'clipboard-clear'});assert.equal(service.snapshot().clipboard.length,0);
  await assert.rejects(service.action({name:'clipboard-copy',value:'missing'}));
  await assert.rejects(service.action({name:'clipboard-pause',value:'true'}));
});
test('download stabilizes once and the same filename can complete again',t=>{
  const {service,downloads,events}=fixture(t);
  const file=path.join(downloads,'example.zip');fs.writeFileSync(file,'a');
  service.scanDownloads();assert.equal(events.length,0);
  service.pending.get('example.zip').since-=5000;service.scanDownloads();
  service.scanDownloads();assert.equal(events.length,1);
  fs.writeFileSync(file,'updated');service.scanDownloads();
  service.pending.get('example.zip').since-=5000;service.scanDownloads();
  // Notification coalescing intentionally suppresses rapid duplicate labels.
  assert.equal(service.pending.size,0);assert.equal(service.seen.get('example.zip').split(':')[0],'7');
  fs.writeFileSync(path.join(downloads,'unfinished.crdownload'),'a');service.scanDownloads();assert.equal(service.pending.size,0);
});
test('task wrapper forwards real success and failure and atomically delivers Unicode text',t=>{
  const {service,events}=fixture(t);
  const script=path.resolve(__dirname,'../../../../scripts/yuki-task.cjs');
  const env={...process.env,YUKI_EVENT_DIR:service.inbox};
  let run=spawnSync(process.execPath,[script,'--',process.execPath,'-e','process.exit(0)'],{env});
  assert.equal(run.status,0,String(run.stderr));service.scanInbox();assert.equal(events[0].kind,'success');
  run=spawnSync(process.execPath,[script,'--',process.execPath,'-e','process.exit(7)'],{env});
  assert.equal(run.status,7);service.scanInbox();assert.equal(events[1].kind,'failure');
  run=spawnSync(process.execPath,[script,'--notify','success','中文编译完成'],{env});
  assert.equal(run.status,0);service.scanInbox();assert.equal(events.at(-1).text,'中文编译完成');
  assert.deepEqual(fs.readdirSync(service.inbox),[]);
});
test('weather sends only an explicit city to HTTPS geocoding and forecast APIs',async()=>{
  const urls=[];const fetchImpl=async url=>{urls.push(url);return Response.json(url.includes('geocoding')?{results:[{name:'杭州',latitude:30,longitude:120}]}:{current:{temperature_2m:20},daily:{temperature_2m_max:[25],temperature_2m_min:[15]}});};
  const result=await weather('杭州',fetchImpl);assert.equal(result.city,'杭州');assert.equal(result.high,25);
  assert.equal(urls.length,2);assert.ok(urls.every(url=>url.startsWith('https://')));
  await assert.rejects(weather(''));
  await assert.rejects(weather('unknown',async()=>Response.json({results:[]})),/没有找到/);
});
test('weather prefers the geocoding entry whose name matches exactly over a pinyin collision',async()=>{
  const urls=[];
  const result=await weather('苏州',async url=>{urls.push(url);return Response.json({results:[{name:'宿州',admin1:'安徽',latitude:33,longitude:118},{name:'苏州',admin1:'江苏',latitude:31,longitude:120}]});});
  assert.equal(result.city,'苏州');assert.match(urls[1],/latitude=31/);
});
test('weather accepts an explicit city only and clears a legacy IP-guessed city',async t=>{
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-weather-legacy-'));
  const downloads=path.join(root,'downloads');fs.mkdirSync(downloads);
  fs.writeFileSync(path.join(root,'desktop.json'),JSON.stringify({city:'Changzhou',cityMode:'ip',clipboardPaused:false}));
  const service=new DesktopServices({app:{getPath:name=>name==='downloads'?downloads:root},powerMonitor:new EventEmitter(),clipboard:{readText:async()=>'',writeText:async()=>{}},fetchImpl:async url=>url.includes('geocoding')?Response.json({results:[{name:'杭州',latitude:30,longitude:120}]}):Response.json({current:{temperature_2m:20},daily:{temperature_2m_max:[25],temperature_2m_min:[15]}}),log:()=>{},spawnImpl:()=>({stdout:{setEncoding(){},on(){},resume(){}},stderr:{resume(){}},on(){},kill(){}})});
  t.after(()=>{service.stop();fs.rmSync(root,{recursive:true,force:true});});
  assert.equal(service.snapshot().city,'');
  assert.equal(JSON.parse(fs.readFileSync(service.settingsPath,'utf8')).city,'');
  await assert.rejects(service.action({name:'weather-guess'}),/未知桌面工具/);
  await service.action({name:'weather',value:'杭州'});
  assert.equal(service.snapshot().city,'杭州');
});
test('the same city reuses cached weather instead of refetching every snapshot',async t=>{
  const {service}=fixture(t);
  let calls=0;
  service.fetchImpl=async url=>{if(url.includes('geocoding'))calls++;return Response.json(url.includes('geocoding')?{results:[{name:'杭州',latitude:30,longitude:120}]}:{current:{temperature_2m:20},daily:{temperature_2m_max:[25],temperature_2m_min:[15]}});};
  await service.action({name:'weather',value:'杭州'});await service.action({name:'weather',value:'杭州'});await service.action({name:'snapshot'});
  assert.equal(calls,1);
  await service.action({name:'weather',value:'苏州'});assert.equal(calls,2);
});
test('snapshots carry clipboard previews and the body is fetched by id',async t=>{
  const {service}=fixture(t);
  const long='长'.repeat(60000);
  service.history.capture(long);
  const snapshot=service.snapshot(),[entry]=snapshot.clipboard;
  assert.equal(entry.text,undefined,'the full body never crosses the snapshot');
  assert.equal(entry.chars,60000);assert.equal(entry.truncated,true);
  assert.equal(entry.preview.length,240);
  assert.ok(JSON.stringify(snapshot).length<4000,`snapshot grew to ${JSON.stringify(snapshot).length} bytes`);
  assert.equal(service.clipboardBody(entry.id),long);
  assert.throws(()=>service.clipboardBody('nope'),/记录编号无效/);
  assert.throws(()=>service.clipboardBody(''),/记录编号无效/);
});
test('an idle desktop stays quiet: unchanged inputs produce no renderer signal',async t=>{
  const {service,write}=fixture(t);
  let signals=0;service.onChanged=()=>signals++;
  await service.readClipboardBaseline();
  await service.readClipboard();await service.readClipboard();
  assert.equal(signals,0,'the same clipboard text is not a change');
  write('新复制的一段话');
  await service.readClipboard();
  assert.equal(signals,1,'a new copy wakes the renderer exactly once');
  await service.readClipboard();
  assert.equal(signals,1,'reading the same text again is still not a change');
  const original={cpus:os.cpus,freemem:os.freemem};
  os.cpus=()=>[{times:{idle:1000,user:0,sys:0,nice:0,irq:0}},{times:{idle:1000,user:0,sys:0,nice:0,irq:0}}];
  os.freemem=()=>1073741824;
  const afterSample=signals;
  service.cpuPrevious={idle:2000,total:2000};
  service.system={cpu:0,memoryUsed:os.totalmem()-1073741824,memoryTotal:os.totalmem()};
  service.sampleSystem();service.sampleSystem();
  assert.equal(signals,afterSample,'identical CPU and memory counters do not wake the renderer');
  os.cpus=original.cpus;os.freemem=original.freemem;
  service.event('download','下载目录已就绪：report.pdf');
  assert.equal(signals,afterSample+1,'events still reach the renderer');
});
test('folder changes go through one debounced scan and polling is only a slow fallback',async t=>{
  const {service,downloads}=fixture(t);
  assert.deepEqual(service.pollerSpecs().map(spec=>spec[1]),[3000,2000,20000,20000],'folders are watched, so the scans drop to 20 seconds');
  fs.writeFileSync(path.join(downloads,'fresh.zip'),'data');
  service.queueScan();service.queueScan();
  await new Promise(resolve=>setTimeout(resolve,400));
  assert.ok(service.pending.has('fresh.zip'),'a single scan runs per burst');
  assert.equal(service.scanQueued,null,'the debounce timer is released');
});
test('collector failures are counted and logged once instead of vanishing',t=>{
  const {service,downloads,logs}=fixture(t);
  fs.rmSync(downloads,{recursive:true,force:true});
  service.scanDownloads();service.scanDownloads();service.scanDownloads();
  assert.equal(service.failures['下载目录扫描'].count,3);
  const lines=logs.filter(line=>line.includes('下载目录扫描'));
  assert.equal(lines.length,1,'only the first trip is logged, the counter keeps the rest');
  assert.match(lines[0],/累计 1 次/);
});
test('model config encrypts credentials, never exposes them, and clears on destination change',async t=>{
  const {root}=fixture(t);const file=path.join(root,'model.json');
  const storage={isAsyncEncryptionAvailable:async()=>true,encryptStringAsync:async s=>Buffer.from('encrypted-'+s),decryptStringAsync:async b=>({result:b.toString().slice(10),shouldReEncrypt:false})};
  const config=new ModelConfig(file,storage);
  await config.ready;await config.set({endpoint:'https://example.com/v1',model:'test',apiKey:'secret'});
  assert.equal(config.key,'secret');assert.equal(config.snapshot().keyPresent,true);
  assert.equal(config.snapshot().apiKey,undefined);assert.notEqual(JSON.parse(fs.readFileSync(file,'utf8')).secret,'secret');
  const reloaded=new ModelConfig(file,storage);await reloaded.ready;assert.equal(reloaded.key,'secret');
  await config.set({endpoint:'https://other.example/v1',model:'test'});assert.equal(config.key,'');
  for(const value of ['http://example.com/v1','file:///bad','https://user:password@example.com','https://example.com/?token=secret'])assert.throws(()=>endpoint(value));
  assert.equal(endpoint('http://127.0.0.1:1234/v1/'),'http://127.0.0.1:1234/v1');
});
test('cloud attachment approval persists for a service and resets when its destination changes',async t=>{
  const {root}=fixture(t);const file=path.join(root,'attachments.json');
  const storage={isAsyncEncryptionAvailable:async()=>true,encryptStringAsync:async s=>Buffer.from('encrypted-'+s),decryptStringAsync:async b=>({result:b.toString().slice(10),shouldReEncrypt:false})};
  const config=new ModelConfig(file,storage);
  await config.ready;
  assert.equal(config.snapshot().allowRemoteAttachments,false);
  assert.equal((await config.setRemoteAttachments(true)).allowRemoteAttachments,true);
  const reloaded=new ModelConfig(file,storage);await reloaded.ready;assert.equal(reloaded.allowRemoteAttachments,true);
  await assert.rejects(config.setRemoteAttachments('yes'),/开关无效/);
  await config.set({endpoint:'https://127.0.0.1:9000/v1',model:'m'});
  await config.setRemoteAttachments(true);
  const reloadedService=new ModelConfig(file,storage);await reloadedService.ready;assert.equal(reloadedService.allowRemoteAttachments,true);
  await config.set({endpoint:'https://127.0.0.1:9000/v1',model:'m'});
  const sameService=new ModelConfig(file,storage);await sameService.ready;assert.equal(sameService.allowRemoteAttachments,true);
  await config.set({endpoint:'https://other.example/v1',model:'m'});
  const afterSave=new ModelConfig(file,storage);await afterSave.ready;assert.equal(afterSave.allowRemoteAttachments,false);
  await config.setRemoteAttachments(false);
  const afterDisable=new ModelConfig(file,storage);await afterDisable.ready;assert.equal(afterDisable.allowRemoteAttachments,false);
});
