'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function run({app,window,sidecar,tray,stopAndQuit,translation,translationWindows}) {
  const results=[];const started=Date.now();
  const request=(name,payload={})=>window.webContents.executeJavaScript(`window.yukiHost.request(${JSON.stringify(name)},${JSON.stringify(payload)})`);
  async function check(name,task,timeout=30000){let timer;try{await Promise.race([task(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Timed out: '+name)),timeout);})]);results.push(name);console.log(`PASS ${name}`);}finally{clearTimeout(timer);}}
  const errors=[];window.webContents.on('console-message',event=>{if(event.level==='error'&&!/Content Security Policy|Refused to connect|Failed to fetch/.test(event.message))errors.push(event.message);});
  await check('preload isolation and bounded API',async()=>{
    assert.equal(await window.webContents.executeJavaScript('typeof require'), 'undefined');
    assert.equal(await window.webContents.executeJavaScript('window.yukiHost.kind'), 'electron');
    assert.equal(await window.webContents.executeJavaScript('Object.keys(window.yukiHost).sort().join(",")'), 'aiAttach,aiCancel,aiChat,aiModels,aiSubscribe,builtinModelSet,desktopAction,desktopSnapshot,desktopSubscribe,exit,kind,modelConfig,modelConfigSet,reconnect,request,subscribe,translationCapture,translationMode,translationSubscribe,windowMode,workbenchConfig,workbenchSet');
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
  const ui=code=>window.webContents.executeJavaScript(code);
  await check('desktop services, model settings and sleep state use real IPC',async()=>{
    const desktop=await ui('window.yukiHost.desktopSnapshot()');
    assert.ok(Array.isArray(desktop.clipboard)&&desktop.clipboard.length<=10);
    assert.ok(Array.isArray(desktop.events));
    assert.equal(typeof desktop.media.available,'boolean');
    assert.equal(typeof desktop.battery.available,'boolean');
    for(const paused of [true,false]){
      assert.equal((await ui(`window.yukiHost.desktopAction({name:'clipboard-pause',value:${paused}})`)).clipboardPaused,paused);
    }
    await assert.rejects(ui(`window.yukiHost.desktopAction({name:'unknown'})`));
    const config=await ui('window.yukiHost.modelConfig()');
    assert.equal(typeof config.endpoint,'string');
    assert.equal(config.apiKey,undefined);
    await assert.rejects(ui(`window.yukiHost.modelConfigSet({endpoint:'http://example.com/v1',model:'test'})`));
    const sleep=(await request('get_state')).state.sleep;
    assert.equal(sleep.schedule,'00:00–07:00 · 13:00–14:00');
    assert.equal(typeof sleep.sleeping,'boolean');
    await assert.rejects(request('desktop_event',{kind:'exec',text:'invalid'}));
    const assets=app.isPackaged?path.join(process.resourcesPath,'pet/python/_internal/assets'):path.resolve(__dirname,'../../../assets');
    for(const index of ['00','48','95'])assert.ok(fs.statSync(path.join(assets,'sleep',index+'.png')).size>0);
    const transitions=path.join(assets,'sleep/transitions');
    const manifest=JSON.parse(fs.readFileSync(path.join(transitions,'manifest.json'),'utf8'));
    assert.equal(manifest.fps,60);
    for(const clip of ['settle','wake']){
      assert.ok(manifest[clip].seconds>0);
      for(let i=0;i<manifest[clip].count;i++)assert.ok(fs.statSync(path.join(transitions,`${clip}-${String(i).padStart(3,'0')}.png`)).size>0);
    }
  });
  // A visible surface is required for fresh compositor frames on Windows.
  if(process.env.YUKI_UI_CAPTURE_DIR){window.showInactive();await wait(300);}
  const navigate=async(label)=>{await ui(`[...document.querySelectorAll('nav button')].find(b=>b.getAttribute('aria-label')===${JSON.stringify(label)}).click()`);await wait(220);};
  const capture=async(name)=>{
    if(!process.env.YUKI_UI_CAPTURE_DIR)return;
    const folder=path.resolve(process.env.YUKI_UI_CAPTURE_DIR);fs.mkdirSync(folder,{recursive:true});
    // Freeze decoration for deterministic screenshots without persisting it.
    const motion=await ui(`document.documentElement.dataset.motion`);
    await ui(`document.documentElement.dataset.motion='reduced'`);
    await wait(500);let frame;
    for(let attempt=0;attempt<3;attempt++){try{frame=await window.webContents.capturePage();break;}catch(error){if(attempt===2)throw error;window.showInactive();await wait(350);}}
    fs.writeFileSync(path.join(folder,name+'.png'),frame.toPNG());
    await ui(`document.documentElement.dataset.motion=${JSON.stringify(motion)}`);
  };
  if(process.env.YUKI_TRANSLATION_SMOKE==='1'){
    await check('translation mode UI starts off and controls native watcher',async()=>{
      await navigate('桌面工具');
      assert.equal((await ui('window.yukiHost.translationMode()')).enabled,false);
      await ui(`document.querySelector('[aria-label="划线翻译模式"]').click()`);await wait(400);
      assert.equal(translation.enabled,true);assert.ok(translation.watcher.child?.pid);
      await ui(`document.querySelector('.translation-panel').scrollIntoView({block:'center'})`);await capture('translation-tools');
      await ui(`document.documentElement.dataset.theme='dark'`);await capture('translation-tools-dark');await ui(`document.documentElement.dataset.theme='light'`);
      window.setSize(880,640);await wait(300);await ui(`document.querySelector('.translation-panel').scrollIntoView({block:'center'})`);await capture('translation-tools-small');
      assert.equal(await ui('document.documentElement.scrollWidth<=innerWidth'),true);window.setSize(1180,820);
      await assert.rejects(ui(`window.yukiHost.translationMode('true')`));
    });
    await check('real local Qwen translation and isolated popup IPC',async()=>{
      await translation.translate('Your download is complete.',{x:450,y:300});
      assert.equal(translation.state.phase,'done',translation.state.error);assert.match(translation.state.text,/[\u4e00-\u9fff]/);
      for(let i=0;i<50&&!translationWindows.popup?.isVisible();i++)await wait(100);
      const popup=translationWindows.popup;assert.ok(popup.isVisible());
      assert.equal(popup.isFocused(),false,'translation popup must not steal keyboard focus');
      assert.equal(await popup.webContents.executeJavaScript('typeof require'),'undefined');
      assert.equal(await popup.webContents.executeJavaScript('typeof window.yukiHost'),'undefined');
      assert.equal(await ui(`typeof window.translation`),'undefined');
      await wait(400);
      if(process.env.YUKI_UI_CAPTURE_DIR)fs.writeFileSync(path.join(process.env.YUKI_UI_CAPTURE_DIR,'translation-popup.png'),(await popup.webContents.capturePage()).toPNG());
      await translation.translate('请重新启动应用。',{x:450,y:300});
      assert.equal(translation.state.phase,'done',translation.state.error);assert.equal(translation.state.target,'English');assert.match(translation.state.text,/[a-z]{3}/i);
      const snapshot=translation.snapshot();
      translation.update({text:'这是用于检查长译文滚动与布局的测试文字。'.repeat(50)});await wait(200);
      assert.equal(await popup.webContents.executeJavaScript('document.documentElement.scrollWidth<=innerWidth'),true);
      translation.update(snapshot);
    },120000);
    await check('OCR region IPC uses offline recognizer and local Qwen',async()=>{
      const {nativeImage}=require('electron');const image=nativeImage.createFromPath(process.env.YUKI_OCR_FIXTURE);
      const service=translationWindows.desktopCapturer,original=service.getSources;
      const display=translationWindows.screen.getDisplayNearestPoint(translationWindows.screen.getCursorScreenPoint());
      try{
        // Use a public fixture instead of retaining a screenshot of the user's desktop.
        service.getSources=async()=>[{display_id:String(display.id),thumbnail:image}];
        await translationWindows.capture();const overlay=translationWindows.overlay;assert.ok(overlay.isVisible());
        assert.equal(await overlay.webContents.executeJavaScript('typeof require'),'undefined');
        await assert.rejects(overlay.webContents.executeJavaScript(`window.capture.region({x:-1,y:0,width:100,height:100})`));
        await overlay.webContents.executeJavaScript(`void window.capture.region({x:0,y:0,width:${display.size.width},height:${display.size.height}})`);
        for(let i=0;i<1200&&!['done','error'].includes(translation.state.phase);i++)await wait(100);
        assert.equal(translation.state.phase,'done',translation.state.error);assert.equal(translation.state.method,'ocr');assert.ok(translation.state.source.length>5);
      }finally{service.getSources=original;}
      await ui('window.yukiHost.translationMode(false)');assert.equal(translation.watcher.child,null);
      assert.equal(translationWindows.popup?.isVisible(),false);assert.equal(translationWindows.overlay,null);
    },150000);
  }
  if(process.env.YUKI_ATTACHMENT_FIXTURES)await check('attachment dialog, local parsers, preview and removal',async()=>{
    const fixture=path.resolve(process.env.YUKI_ATTACHMENT_FIXTURES);
    const {Attachments}=require('./attachments.cjs');const store=new Attachments();
    for(const name of ['fixture.pdf','fixture.docx']){
      const metadata=await store.add(path.join(fixture,name));assert.match(store.resolve([metadata.id])[0].text,/Yuki/);
    }
    const {dialog}=require('electron');const original=dialog.showOpenDialog;
    await navigate('AI 助手');
    try{
      const image=process.env.YUKI_OCR_FIXTURE;assert.ok(image,'YUKI_OCR_FIXTURE must be a text image');
      dialog.showOpenDialog=async()=>({canceled:false,filePaths:[path.join(fixture,'fixture.docx'),path.resolve(image)]});
      await ui(`document.querySelector('[aria-label="添加图片或文档"]').click()`);
      for(let i=0;i<250;i++){if(await ui(`document.querySelectorAll('[aria-label="待发送附件"] .chat-file').length===2`))break;await wait(100);}
      assert.equal(await ui(`document.querySelectorAll('[aria-label="待发送附件"] .chat-file').length`),2);
      assert.equal(await ui(`document.querySelector('[aria-label="待发送附件"] img').naturalWidth>0`),true);
      assert.ok(await ui(`document.querySelector('[aria-label="待发送附件"]').textContent.includes('OCR 已提取')`));
      await capture('attachments-desktop');window.setSize(880,640);await wait(300);await capture('attachments-small');
      assert.ok(await ui('document.documentElement.scrollWidth<=innerWidth'));
      await ui(`document.querySelector('[aria-label="移除 fixture.docx"]').click()`);
      assert.equal(await ui(`document.querySelectorAll('[aria-label="待发送附件"] .chat-file').length`),1);
      await ui(`document.querySelector('[aria-label="待发送附件"] button').click()`);
    }finally{dialog.showOpenDialog=original;window.setSize(1180,820);}
  });
  await check('nine workbench pages, assets, planned capability boundaries',async()=>{
    for(const label of ['总览','角色','动作库','动画','行为','音乐互动','AI 助手','桌面工具','设置']){
      await navigate(label);
      assert.equal(await ui(`document.querySelector('nav [aria-current="page"]').getAttribute('aria-label')`),label);
      assert.ok(await ui('document.documentElement.scrollWidth <= innerWidth'),'horizontal overflow: '+label);
      const broken=await ui(`Promise.all([...document.images].map(image=>new Promise(resolve=>{image.loading='eager';if(image.complete)return resolve(!image.naturalWidth);image.onload=()=>resolve(false);image.onerror=()=>resolve(true);}))).then(items=>items.some(Boolean))`);
      assert.equal(broken,false,'missing image: '+label);
      if(label==='桌面工具')assert.ok(await ui(`!!document.querySelector('.desktop-clock time') && !!document.querySelector('.clipboard-panel') && !!document.querySelector('.media-panel')`));
      if(['总览','动作库','音乐互动','AI 助手','桌面工具','设置'].includes(label))await capture('light-'+label);
    }
    await navigate('总览');
    assert.equal(await ui(`document.body.innerText.includes('跳一下') || document.body.innerText.includes('轻轻一跃')`),false);
    assert.equal(await ui(`document.querySelectorAll('.featured-motion').length`),4);
  });
  await check('four idle states classify real assets and filtering stays local',async()=>{
    await navigate('动作库');
    const config=await ui(`fetch('/actions/idle-states.json').then(response=>response.json())`);
    const entries=await ui(`fetch('/actions/catalog.json').then(response=>response.json())`);
    assert.deepEqual(config.states.map(state=>state.id),['sleep','stand','sit','prone']);
    const idle=(await request('get_state')).state.idle;
    assert.equal(typeof idle.name,'string');
    assert.equal(typeof idle.automatic,'boolean');
    for(const state of config.states){
      await ui(`document.querySelector('[data-idle-state="${state.id}"]').click()`);await wait(100);
      const ids=await ui(`[...document.querySelectorAll('.action-tile')].map(button=>button.dataset.actionId)`);
      assert.deepEqual([...ids].sort(),[...state.actions].sort());
      assert.equal(await ui(`document.querySelector('[data-idle-state="${state.id}"]').getAttribute('aria-pressed')`),'true');
      for(const key of ids)assert.equal(entries.find(entry=>entry.id===key).idle_state,state.id);
      if(['sleep','sit','prone'].includes(state.id))await capture('idle-'+state.id);
    }
    await ui(`document.querySelector('[data-idle-state="sleep"]').click()`);await wait(80);
    for(const key of ['sleep-enter','sleep','sleep-wake']){
      await ui(`document.querySelector('[data-action-id="${key}"]').click()`);await wait(100);
      assert.equal(await ui(`!!document.querySelector('.save-error')`),false);
      assert.ok(await ui(`document.querySelector('.action-state-note').textContent.includes('睡觉待机')`));
    }
    await ui(`document.querySelector('[data-idle-state="all"]').click()`);await wait(80);
    await navigate('总览');
  });
  await check('music playback status and persistent switch reach backend',async()=>{
    await navigate('音乐互动');
    assert.ok(await ui(`!!document.querySelector('[role="meter"][aria-label="系统播放音量"]')`));
    await ui(`document.querySelector('[role="switch"][aria-label="随声音互动"]').click()`);await wait(400);
    assert.equal((await request('get_state')).state.preferences.music_reactions,false);
    await ui(`document.querySelector('[role="switch"][aria-label="随声音互动"]').click()`);await wait(500);
    const state=(await request('get_state')).state;
    assert.equal(state.preferences.music_reactions,true);
    assert.equal(typeof state.music.listening,'boolean');
    assert.ok(Array.isArray(state.music.bands));
    await assert.rejects(request('set_preference',{key:'music_reactions',value:'yes'}));
    await navigate('总览');
  });
  await check('real UI toggle reaches sidecar and action preview remains local',async()=>{
    await ui(`document.querySelector('[role="switch"][aria-label="拖放即时吸附"]').click()`);await wait(300);
    assert.equal((await request('get_state')).state.preferences.auto_snap,false);
    await ui(`document.querySelector('[role="switch"][aria-label="拖放即时吸附"]').click()`);await wait(300);
    assert.equal((await request('get_state')).state.preferences.auto_snap,true);
    await ui(`document.querySelectorAll('.featured-motion')[1].click()`);await wait(300);
    assert.equal(await ui(`document.querySelector('.action-viewer h2').textContent`),'看书');
    await ui(`document.querySelector('[aria-label="暂停预览"]').click()`);
    await ui(`(()=>{const input=document.querySelector('[aria-label="逐帧查看"]');const set=Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set;set.call(input,'2');input.dispatchEvent(new Event('input',{bubbles:true}));input.dispatchEvent(new Event('change',{bubbles:true}));})()`);await wait(150);
    assert.equal(await ui(`document.querySelector('[aria-label="逐帧查看"]').value`),'2');
  });
  await check('themes, reduced motion persistence and minimum window layout',async()=>{
    await navigate('设置');
    await ui(`document.querySelector('[aria-label="切换深色主题"]').click()`);
    await ui(`document.querySelector('[role="switch"][aria-label="减少动态效果"]').click()`);await wait(100);
    assert.equal(await ui(`document.documentElement.dataset.motion`),'reduced');
    await window.webContents.reload();await wait(700);
    assert.equal(await ui(`document.documentElement.dataset.theme`),'dark');
    assert.equal(await ui(`document.documentElement.dataset.motion`),'reduced');
    await capture('dark-overview');
    await navigate('桌面工具');await capture('dark-desktop');
    await navigate('设置');await ui(`document.querySelector('[role="switch"][aria-label="减少动态效果"]').click()`);
    await ui(`document.querySelector('[aria-label="切换浅色主题"]').click()`);
    window.setSize(880,640);
    assert.ok(await ui(`[...document.querySelectorAll('nav button')].every(button=>button.getBoundingClientRect().bottom<=innerHeight)`),'navigation must fit the minimum window height');
    for(const label of ['总览','动作库','行为','音乐互动','AI 助手','桌面工具','设置']){await navigate(label);assert.ok(await ui('document.documentElement.scrollWidth <= innerWidth'),'minimum width overflow: '+label);if(['总览','动作库','行为','桌面工具'].includes(label))await capture('small-'+label);}
    window.setSize(1180,820);await navigate('总览');
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
  await check('desktop speech route and plain-text paged replies',async()=>{
    const reply=await request('speech_update',{id:'smoke-speech',phase:'done',text:'你好。'.repeat(90)});
    assert.equal(reply.state.speech.active,true);
    assert.equal(reply.state.speech.kind,'chat');
    assert.ok(reply.state.speech.pages>1);
    assert.equal(reply.state.speech.pending,false);
    assert.equal(typeof reply.state.routine.name,'string');
    assert.equal(typeof reply.state.patrol.active,'boolean');
    assert.ok(['idle','walking','doing','resting'].includes(reply.state.patrol.phase));
    assert.ok(['night','morning','focus','noon','nap','afternoon','evening','winddown'].includes(reply.state.routine.key));
    await assert.rejects(request('speech_update',{id:'bad',phase:'system',text:'override'}));
  });
  await check('full-colour lazy roll atlases and frozen backend playback',async()=>{
    const entries=await ui(`fetch('/actions/catalog.json').then(response=>response.json())`);
    assert.deepEqual(entries.filter(entry=>entry.id.includes('roll')).map(entry=>entry.id).sort(),['lazy-roll-away','lazy-roll-toward']);
    assert.ok(entries.length>0&&entries.every(entry=>entry.scale_calibrated===true),'Every action must use calibrated sprites');
    for(const id of ['lazy-roll-toward','lazy-roll-away']){
      const action=entries.find(entry=>entry.id===id);
      assert.ok(action?.lazy_roll&&!action.pixel_art);
      assert.equal(action.frames,12);
      const dimensions=await ui(`new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve([image.naturalWidth,image.naturalHeight]);image.onerror=()=>reject(new Error('Missing lazy roll atlas'));image.src=${JSON.stringify('/'+action.atlas)};})`);
      assert.deepEqual(dimensions,[1024,768]);
      assert.equal((await request('play_action',{action_id:id})).ok,true);
      await wait(100);await request('stop_action');
    }
  });
  await check('reviewed pose transitions are bundled and frozen actions play',async()=>{
    const assets=app.isPackaged?path.join(process.resourcesPath,'pet/python/_internal/assets'):path.resolve(__dirname,'../../../assets');
    const motion=path.join(assets,'action-motion');
    const manifestBytes=fs.readFileSync(path.join(motion,'manifest.json'));
    const manifest=JSON.parse(manifestBytes);
    const entries=await ui(`fetch('/actions/catalog.json').then(response=>response.json())`);
    const {createHash}=require('node:crypto');
    assert.ok(Object.keys(manifest.pairs).length>200);
    for(const entry of Object.values(manifest.pairs)){
      assert.equal(entry.frames,25,'Keep the density of the reviewed preview');
      assert.ok(fs.statSync(path.join(motion,entry.file)).size>0);
    }
    for(const [id,digest] of Object.entries(manifest.source_sha256)){
      assert.ok(entries.find(entry=>entry.id===id),'Missing source action: '+id);
      // The console mirror is lossless WebP; the review digest covers the
      // runtime PNG that the frozen backend ships.
      assert.equal(createHash('sha256').update(fs.readFileSync(path.join(assets,'actions',id,'atlas.png'))).digest('hex'),digest);
    }
    if(app.isPackaged)assert.equal(fs.existsSync(path.join(process.resourcesPath,'pet/assets')),false,'Duplicate pet assets');
    // At nap time, complete the real wake transition before checking action labels.
    await request('wake_sleep');
    for(let i=0;i<70;i++){if((await request('get_state')).state.sleep.phase!=='waking')break;await wait(100);}
    for(const id of ['sit-neat','prone-rest','stretch','lazy-roll-toward','lazy-roll-away']){
      const played=await request('play_action',{action_id:id});
      assert.equal(played.ok,true);
      assert.ok(played.state.status.includes(entries.find(entry=>entry.id===id).name),id+': '+played.state.status);
      await wait(1200);await request('stop_action');
    }
  });
  await check('front and reverse lazy rolls travel across the head-to-feet axis',async()=>{
    await request('set_preference',{key:'random_movement',value:false});
    await request('set_preference',{key:'music_reactions',value:false});
    for(const [action,direction] of [['lazy-roll-toward',-1],['lazy-roll-away',1]]){
      const before=(await request('play_action',{action_id:action})).state.position;
      // Let the first roll clear the boundary fallback zone before reversing.
      await wait(9000);
      const after=(await request('get_state')).state.position;
      assert.ok((after.y-before.y)*direction>8,action+' must move perpendicular to its head-to-feet axis: '+JSON.stringify({before,after,direction}));
      assert.equal(after.x,before.x,action+' must preserve its lateral line');
      await request('stop_action');await wait(150);
    }
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
  if(process.env.YUKI_AI_SMOKE==='1'){
    window.showInactive();
    await navigate('AI 助手');
    const ask=async text=>{
      await ui(`(()=>{const input=document.querySelector('textarea[aria-label="对话输入"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,${JSON.stringify(text)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      await wait(150);await ui(`document.querySelector('button[aria-label="发送消息"]').click()`);
      for(let i=0;i<850;i++){
        await wait(100);
        if(await ui(`!document.querySelector('button[aria-label="停止回复"]')`)){
          const failure=await ui(`document.querySelector('.chat-error')?.textContent||''`);assert.equal(failure,'');
          return ui(`document.querySelector('.chat-turn.assistant:last-of-type p')?.textContent||[...document.querySelectorAll('.chat-turn.assistant p')].at(-1)?.textContent||''`);
        }
      }throw new Error('Local model reply timed out');
    };
    await check('local model discovery through guarded Electron IPC',async()=>{
      const result=await ui('window.yukiHost.aiModels()');assert.ok(result.models.some(id=>id.includes('qwen3.8')));
      for(let i=0;i<30;i++){if(await ui(`!!document.querySelector('#ai-model')?.value`))return;await wait(100);}throw Error('No selected model');
    });
    await check('real React chat receives a Chinese persona response',async()=>{
      const answer=await ask('你好，你叫什么名字？用一句话介绍你自己。');assert.match(answer,/雪|yuki/i);assert.doesNotMatch(answer,/<think>/);await capture('ai-real-conversation');
    },90000);
    await check('multi-turn chat remembers information in current conversation',async()=>{
      const answer=await ask('我给你准备了一杯茉莉花茶，请记住这个茶名，并用一句话回应。');assert.match(answer,/茉莉/);
    },90000);
    await check('chat survives page navigation and recalls the tea',async()=>{
      await navigate('角色');await navigate('AI 助手');await wait(300);
      assert.equal(await ui(`document.querySelectorAll('.chat-turn').length`),4);
      const answer=await ask('刚刚我给你准备的是什么茶？只回答茶名。');assert.match(answer,/茉莉/);await capture('ai-memory');
    },90000);
    await check('stop generation returns the chat to an editable state',async()=>{
      await ui(`(()=>{const input=document.querySelector('textarea');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'请详细介绍你喜欢的十种茶。');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      await wait(150);await ui(`document.querySelector('button[aria-label="发送消息"]').click()`);await wait(200);
      await ui(`document.querySelector('button[aria-label="停止回复"]').click()`);
      for(let i=0;i<50;i++){if(await ui(`!document.querySelector('textarea').disabled`))return;await wait(100);}throw Error('Cancellation did not release composer');
    });
  }
  assert.deepEqual(errors,[],'renderer console errors');
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
