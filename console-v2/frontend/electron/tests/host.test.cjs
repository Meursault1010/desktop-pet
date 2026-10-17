const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {Sidecar}=require('../main/sidecar.cjs');
const {validate}=require('../shared/protocol.cjs');
const {resourcePath,trusted,webPreferences,closeBehavior}=require('../main/security.cjs');
const create=options=>new Sidecar({command:process.execPath,args:[path.join(__dirname,'fixture.cjs')],timeout:100,readyTimeout:1000,...options});
test('schema blocks unknown, paths, bool integers, invalid edge options',()=>{
  for(const [name,payload] of [['exec',{}],['set_preference',{key:'size',value:true}],['play_action',{action_id:'../bad'}],
    ['configure_edge_attachment',{delay:true}],['get_state',{path:'secret'}],['configure_icon_sleep',{direction:'bad'}]])assert.throws(()=>validate(name,payload));
  validate('set_preference',{key:'auto_snap',value:true});validate('play_action',{action_id:'screen',loop:true,speed:2});
});
test('resource allowlist and traversal protection',()=>{
  const root=path.resolve('dist');assert.equal(resourcePath('yuki://app/actions/sleep/atlas.png',root),path.join(root,'actions/sleep/atlas.png'));
  for(const url of ['file:///etc/passwd','yuki://evil/index.html','yuki://app/%2e%2e%2fsecret','yuki://app/a%5c..%5csecret'])assert.throws(()=>resourcePath(url,root));
});
test('only console main frame may call IPC',()=>{
  const frame={url:'yuki://app/index.html'},wc={mainFrame:null};wc.mainFrame=frame;
  const w={webContents:wc,isDestroyed:()=>false};assert.equal(trusted({sender:wc,senderFrame:frame},w),true);
  assert.equal(trusted({sender:{},senderFrame:frame},w),false);
  assert.equal(trusted({sender:wc,senderFrame:{url:frame.url}},w),false);
});
test('sandbox and close/tray lifecycle decisions',()=>{
  assert.deepEqual(webPreferences('preload'),{preload:'preload',nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,webviewTag:false});
  assert.equal(closeBehavior({quitting:false,trayReady:true}),'hide');assert.equal(closeBehavior({quitting:false,trayReady:false}),'minimize');
  assert.equal(closeBehavior({quitting:true,trayReady:true}),'close');
});
test('spawn once, readiness, request, bounded queue and exit cleanup',async()=>{
  const s=create({maxPending:1});try{await Promise.all([s.start(),s.start()]);const pid=s.child.pid;
    assert.equal((await s.request('get_state')).ok,true);assert.equal(s.child.pid,pid);
    const delayed=s.request('set_preference',{key:'opacity',value:90});
    await assert.rejects(s.request('get_state'),/队列/);await assert.rejects(delayed,/超时/);assert.equal(s.pending.size,0);
  }finally{await s.stop();}assert.equal(s.child,null);
});
test('incompatible protocol fails startup and cleans up',async()=>{
  const s=create({args:[path.join(__dirname,'fixture.cjs'),'bad-version']});try{await assert.rejects(s.start(),/版本/);}finally{await s.stop();}
});
test('invalid JSON rejects pending requests without hanging',async()=>{
  const s=create();try{await s.start();await assert.rejects(s.request('jump'));}finally{await s.stop();}assert.equal(s.pending.size,0);
});
test('crash disconnects then reconnect starts a fresh child',async()=>{
  const s=create();try{await s.start();const pid=s.child.pid;
    const closed=new Promise(resolve=>s.once('disconnected',resolve));s.child.kill();await closed;
    await new Promise(resolve=>setTimeout(resolve,550));await s.start();assert.notEqual(s.child.pid,pid);await s.request('get_state');
  }finally{await s.stop();}
});
test('missing interpreter rejects instead of hanging',async()=>{
  const s=create({command:path.join(__dirname,'missing-python.exe')});try{await assert.rejects(s.start(),/启动失败/);}finally{await s.stop();}
});
