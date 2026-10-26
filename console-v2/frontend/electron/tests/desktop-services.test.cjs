const {test}=require('node:test');
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
  const events=[];let copied='original';
  const app={getPath:name=>name==='downloads'?downloads:root};
  const powerMonitor=new EventEmitter();
  const service=new DesktopServices({app,powerMonitor,clipboard:{readText:async()=>copied,writeText:async value=>{copied=value;}},react:e=>events.push(e)});
  t.after(()=>{service.stop();fs.rmSync(root,{recursive:true,force:true});});
  return {root,downloads,events,service,powerMonitor,read:()=>copied};
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
test('model config encrypts credentials, never exposes them, and clears on destination change',t=>{
  const {root}=fixture(t);const file=path.join(root,'model.json');
  const storage={isEncryptionAvailable:()=>true,encryptString:s=>Buffer.from('encrypted-'+s),decryptString:b=>b.toString().slice(10)};
  const config=new ModelConfig(file,storage);
  config.set({endpoint:'https://example.com/v1',model:'test',apiKey:'secret'});
  assert.equal(config.key,'secret');assert.equal(config.snapshot().keyPresent,true);
  assert.equal(config.snapshot().apiKey,undefined);assert.notEqual(JSON.parse(fs.readFileSync(file,'utf8')).secret,'secret');
  assert.equal(new ModelConfig(file,storage).key,'secret');
  config.set({endpoint:'https://other.example/v1',model:'test'});assert.equal(config.key,'');
  for(const value of ['http://example.com/v1','file:///bad','https://user:password@example.com','https://example.com/?token=secret'])assert.throws(()=>endpoint(value));
  assert.equal(endpoint('http://127.0.0.1:1234/v1/'),'http://127.0.0.1:1234/v1');
});
