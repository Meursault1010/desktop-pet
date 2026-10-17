'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function run({app,window,sidecar,tray,stopAndQuit}) {
  const results=[];const started=Date.now();
  const request=(name,payload={})=>window.webContents.executeJavaScript(`window.yukiHost.request(${JSON.stringify(name)},${JSON.stringify(payload)})`);
  async function check(name,task){await task();results.push(name);console.log(`PASS ${name}`);}
  const errors=[];window.webContents.on('console-message',event=>{if(event.level==='error'&&!/Content Security Policy|Refused to connect|Failed to fetch/.test(event.message))errors.push(event.message);});
  await check('preload isolation and bounded API',async()=>{
    assert.equal(await window.webContents.executeJavaScript('typeof require'), 'undefined');
    assert.equal(await window.webContents.executeJavaScript('window.yukiHost.kind'), 'electron');
    assert.equal(await window.webContents.executeJavaScript('Object.keys(window.yukiHost).sort().join(",")'), 'exit,kind,reconnect,request,subscribe');
    assert.equal(window.webContents.getLastWebPreferences().sandbox,true);
  });
  await check('React UI connected through Electron IPC',async()=>{
    for(let i=0;i<100;i++){
      if(await window.webContents.executeJavaScript('document.body.innerText.includes("本地已连接")'))return;
      await wait(100);
    }
    throw new Error('React connection badge missing');
  });
  await check('all preview image resources load',async()=>{
    const broken=await window.webContents.executeJavaScript(`Promise.all([...document.images].map(image=>new Promise(resolve=>{
      if(image.complete)return resolve(image.naturalWidth?null:image.src);
      image.onload=()=>resolve(null);image.onerror=()=>resolve(image.src);
    }))).then(values=>values.filter(Boolean))`);
    assert.deepEqual(broken,[]);
  });
  await check('reject unknown command, invalid preference and path traversal',async()=>{
    await assert.rejects(request('exec',{command:'whoami'}));
    await assert.rejects(request('set_preference',{key:'size',value:999}));
    await assert.rejects(request('play_action',{action_id:'../../bad'}));
    assert.equal(await window.webContents.executeJavaScript('fetch("yuki://app/%2e%2e%2fpackage.json").then(r=>r.status)'),404);
  });
  await check('visibility, preferences, action, edge configuration',async()=>{
    assert.equal((await request('set_visible',{visible:false})).state.visible,false);
    assert.equal((await request('set_visible',{visible:true})).state.visible,true);
    assert.equal((await request('set_preference',{key:'size',value:105})).state.preferences.size,105);
    assert.equal((await request('set_preference',{key:'auto_snap',value:false})).state.preferences.auto_snap,false);
    assert.equal((await request('set_preference',{key:'auto_snap',value:true})).state.preferences.auto_snap,true);
    assert.equal((await request('configure_edge_attachment',{enabled:true,delay:2})).state.edge_attachment.options.enabled,true);
    await request('configure_edge_attachment',{enabled:false});
    await request('play_action',{action_id:'screen',loop:true,speed:1});await request('stop_action');
    await request('jump');await request('go_home');await request('refresh_desktop_icons');
  });
  await check('backend crash and reconnect restores saved preference',async()=>{
    const closed=new Promise(resolve=>sidecar.once('disconnected',resolve));sidecar.child.kill();await closed;
    await wait(600);await window.webContents.executeJavaScript('window.yukiHost.reconnect()');
    assert.equal((await request('get_state')).state.preferences.size,105);
  });
  await check('console close keeps backend, reopen connects',async()=>{
    assert.ok(tray&&!tray.isDestroyed(),'Windows system tray was not created');
    const pid=sidecar.child.pid;window.close();assert.equal(window.isDestroyed(),false);
    assert.equal(window.isVisible(),false);
    assert.equal(sidecar.child.pid,pid);window.restore();
    assert.equal((await request('get_state')).type,'response');
  });
  if(app.isPackaged)await check('second launch reuses existing instance and backend',async()=>{
    const {spawn}=require('node:child_process');const pid=sidecar.child.pid;
    const duplicate=spawn(process.execPath,['--smoke-test'],{env:process.env,stdio:'ignore',windowsHide:true});
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>{duplicate.kill();reject(new Error('Duplicate instance did not exit'));},8000);
      duplicate.once('error',error=>{clearTimeout(timer);reject(error);});
      duplicate.once('exit',code=>{clearTimeout(timer);if(code===0)resolve();else reject(new Error(`Duplicate exit ${code}`));});});
    assert.equal(sidecar.child.pid,pid);assert.equal((await request('get_state')).ok,true);
  });
  await check('renderer cannot create new windows or use external network',async()=>{
    assert.equal(await window.webContents.executeJavaScript('window.open("https://example.com") === null'),true);
    assert.equal(await window.webContents.executeJavaScript('fetch("https://example.com").then(()=>false,()=>true)'),true);
  });
  const child=sidecar.child;
  await sidecar.stop();assert.equal(sidecar.child,null);assert.notEqual(child.exitCode,null);
  results.push('exit cleans up backend');
  const output={passed:results.length,results,consoleErrors:errors,durationMs:Date.now()-started,
    versions:process.versions,renderer:'PySide6 compatibility',backendExited:true};
  const target=process.env.YUKI_SMOKE_REPORT;
  if(target){fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,JSON.stringify(output,null,2));}
  console.log(JSON.stringify(output));await stopAndQuit();
}
module.exports={run};
