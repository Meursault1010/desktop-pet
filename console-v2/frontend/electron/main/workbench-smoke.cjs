'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const wait=ms=>new Promise(r=>setTimeout(r,ms));
async function run({window,sidecar,stopAndQuit,quickTools}){
 const results=[],errors=[],started=Date.now(),folder=process.env.YUKI_UI_CAPTURE_DIR;
 const ui=s=>window.webContents.executeJavaScript(s);
 window.webContents.on('console-message',e=>{if(e.level==='error'&&!/Failed to fetch|ERR_CONNECTION_REFUSED/.test(e.message))errors.push(e.message);});
 const click=async text=>{const ok=await ui(`(()=>{const b=[...document.querySelectorAll('button')].find(x=>x.offsetParent&&x.textContent.trim()===${JSON.stringify(text)});if(!b)return false;b.click();return true;})()`);assert.ok(ok,'missing button '+text);await wait(180);};
 const nav=async label=>{await ui(`document.querySelector('nav [aria-label=${JSON.stringify(label)}]').click()`);await wait(200);};
 const field=async(label,value)=>{await ui(`(()=>{const e=document.querySelector('[aria-label=${JSON.stringify(label)}]');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,${JSON.stringify(value)});e.dispatchEvent(new Event('input',{bubbles:true}));})()`);await wait(80);};
 const capture=async name=>{if(!folder)return;fs.mkdirSync(folder,{recursive:true});await ui(`document.documentElement.dataset.motion='reduced';document.querySelector('main').scrollTo(0,0)`);window.showInactive();await wait(450);fs.writeFileSync(path.join(folder,name+'.png'),(await window.webContents.capturePage()).toPNG());};
 async function check(name,fn){await fn();results.push(name);console.log('PASS '+name);}
 await check('Electron preload isolation, complete navigation, and backend connection',async()=>{
  assert.equal(await ui('typeof require'),'undefined');assert.equal(window.webContents.getLastWebPreferences().sandbox,true);
  for(let i=0;i<80;i++){if(await ui(`document.querySelector('.nav-foot').textContent.includes('桌宠已连接')`))break;await wait(100);}
  assert.equal(await ui(`document.querySelectorAll('nav button').length`),5);assert.ok(await ui(`document.querySelector('.nav-foot').textContent.includes('桌宠已连接')`),await ui('document.body.innerText')); 
  assert.ok((await ui('window.yukiHost.desktopSnapshot()')).system.memoryTotal>0);
  const petAsset=await ui(`new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve([image.naturalWidth,image.naturalHeight]);image.onerror=()=>reject(new Error('Missing pet asset route'));image.src='/pet-assets/living-idle/open.png';})`);
  assert.deepEqual(petAsset,[2048,2048]);
 });
 if(process.env.YUKI_PLAY_SMOKE==='1'){
  await nav('角色');await click('行为逻辑');
  await check('autoplay switches use real IPC and remain independent of drag snap',async()=>{
   for(const [key,label] of [['autonomous_play','自主玩耍'],['autonomous_icons','自主图标互动'],['autonomous_speech','自主短句']]){
    const before=(await sidecar.request('get_state')).state.preferences;
    await ui(`document.querySelector('[role=switch][aria-label=${JSON.stringify(label)}]').click()`);await wait(300);
    const after=(await sidecar.request('get_state')).state;
    assert.equal(after.preferences[key],!before[key]);assert.equal(after.preferences.auto_snap,before.auto_snap);
    assert.equal(typeof after.patrol.next_intent,'string');assert.equal(typeof after.patrol.reason,'string');
    assert.equal(typeof after.patrol.target,'string');assert.equal(typeof after.patrol.path_probe_ms,'number');
    await sidecar.request('set_preference',{key,value:before[key]});await wait(150);
   }
  });
  assert.ok(await ui(`document.querySelector('.behavior-now').textContent.includes('当前目标：')`));
  await check('behavior page fits all themes in compact and expanded windows',async()=>{
   for(const size of [[900,640],[1180,820]]){
    window.setSize(...size);
    for(const theme of ['mist','light','dark']){
     await ui(`document.documentElement.dataset.theme=${JSON.stringify(theme)}`);await wait(150);
     assert.ok(await ui('document.documentElement.scrollWidth<=innerWidth'));
     await capture('autoplay-'+theme+'-'+size[0]);
    }
   }
  });
  assert.deepEqual(errors,[]);console.log(JSON.stringify({passed:results,errors}));await stopAndQuit();return;
 }
 if(process.env.YUKI_SCROLL_SMOKE==='1'){
  window.setSize(900,640);window.show();window.focus();await wait(500);
  const metrics=()=>ui(`(()=>{const m=document.querySelector('main'),r=m.getBoundingClientRect(),s=getComputedStyle(m);return {height:m.clientHeight,content:m.scrollHeight,top:m.scrollTop,bottom:r.bottom,viewport:innerHeight,margin:s.margin,overflow:s.overflowY};})()`);
  console.log('SCROLL_METRICS',JSON.stringify(await metrics()));
  await check('compact workbench responds to real wheel input',async()=>{
   const before=await metrics();assert.ok(before.content>before.height,'page needs an actual scroll viewport');assert.ok(before.bottom<=before.viewport+1,'main must stay inside the window');
   window.webContents.sendInputEvent({type:'mouseMove',x:700,y:500});await wait(100);
   window.webContents.sendInputEvent({type:'mouseWheel',x:700,y:500,deltaX:0,deltaY:-400,canScroll:true});await wait(500);
   assert.ok((await metrics()).top>0,'real mouse wheel must move page');
   await ui(`document.querySelector('main').scrollTo(0,100000)`);await wait(100);
   assert.ok(await ui(`(()=>{const r=document.querySelector('.workbench-footer').getBoundingClientRect();return r.bottom<=innerHeight+1})()`),'footer reachable');
  });
  await check('settings scroll in all themes and expanded window stays bounded',async()=>{
   await nav('设置');await click('通用');
   for(const theme of ['mist','light','dark']){
    await ui(`document.documentElement.dataset.theme=${JSON.stringify(theme)};document.querySelector('main').scrollTo(0,0)`);await wait(120);
    const before=await metrics();assert.ok(before.content>before.height);
    window.webContents.sendInputEvent({type:'mouseMove',x:90,y:400});await wait(80);
    window.webContents.sendInputEvent({type:'mouseWheel',x:90,y:400,deltaX:0,deltaY:-300,canScroll:true});await wait(350);
    assert.ok((await metrics()).top>0,'settings wheel '+theme);
   }
   window.setSize(1180,820);await wait(250);const m=await metrics();assert.ok(m.bottom<=m.viewport+1);
   window.setSize(900,640);await nav('总览');await ui(`document.querySelector('main').scrollTo(0,100000)`);await wait(200);
  });
  if(process.env.YUKI_UI_CAPTURE_DIR){fs.mkdirSync(process.env.YUKI_UI_CAPTURE_DIR,{recursive:true});fs.writeFileSync(path.join(process.env.YUKI_UI_CAPTURE_DIR,'scrolled-overview.png'),(await window.webContents.capturePage()).toPNG());}
  console.log(JSON.stringify({passed:results,metrics:await metrics()}));await stopAndQuit();return;
 }
 await check('native quick tools share renderer todos and focus through real IPC',async()=>{
  assert.ok(quickTools.work);
  await quickTools.action('todo-add',{text:'原生菜单测试事项',minutes:30});await wait(350);
  const todo=quickTools.work.todos.find(t=>t.text==='原生菜单测试事项');assert.ok(todo);assert.ok(todo.due);assert.ok(!todo.due.endsWith('Z'));
  await quickTools.action('todo-done',todo.id);await wait(350);assert.ok(quickTools.work.todos.find(t=>t.id===todo.id).done);
  await quickTools.action('focus-reset');await wait(150);
  await quickTools.action('focus-toggle');await wait(350);assert.ok(quickTools.work.focus.end);assert.equal(await ui('document.documentElement.dataset.focus'),'true');
  await quickTools.action('focus-toggle');await wait(350);assert.equal(quickTools.work.focus.end,null);
  await quickTools.action('snapshot');
 });
 if(process.env.YUKI_QUICK_TOOLS_SMOKE==='1'){
  assert.deepEqual(errors,[]);
  const report={passed:results.length,results,errors,durationMs:Date.now()-started};
  if(process.env.YUKI_SMOKE_REPORT){fs.mkdirSync(path.dirname(process.env.YUKI_SMOKE_REPORT),{recursive:true});fs.writeFileSync(process.env.YUKI_SMOKE_REPORT,JSON.stringify(report,null,2));}
  console.log(JSON.stringify(report));await stopAndQuit();return;
 }
 await check('five sections and every subpage render without overflow or missing assets',async()=>{
  for(const [section,tabs] of Object.entries({'总览':[],'角色':['音乐互动','动作','外观','行为逻辑'],'AI 助手':['与雪对话','模型连接'],'工具':['时间管理','剪贴板','待办事项','划词翻译'],'设置':['通用','主题与动态','快捷键','人设与记忆']})){
   await nav(section);for(const tab of tabs){await click(tab);assert.ok(await ui('document.documentElement.scrollWidth<=innerWidth'),'overflow '+section+tab);await capture(section+'-'+tab);}
  }
  const broken=await ui(`Promise.all([...document.images].filter(i=>i.offsetParent).map(i=>new Promise(r=>{if(i.complete)return r(i.naturalWidth?null:i.src);i.onload=()=>r(null);i.onerror=()=>r(i.src);}))).then(x=>x.filter(Boolean))`);assert.deepEqual(broken,[]);
 });
 await check('navigation, subtabs and nested settings reorder independently and persist',async()=>{
  const reorder=async(scope,index,key)=>{await ui(`(()=>{const group=document.querySelector('[data-sort-scope="${scope}"]');const item=group.querySelectorAll(':scope>.sortable-item')[${index}];const handle=item.querySelector(':scope>.sort-grip')||item.querySelector('button');handle.focus();handle.dispatchEvent(new KeyboardEvent('keydown',{key:'${key}',altKey:true,bubbles:true}));})()`);await wait(300);};
  await reorder('main-navigation',0,'ArrowDown');
  assert.equal(await ui(`document.querySelector('nav button').getAttribute('aria-label')`),'角色');
  await nav('设置');await click('通用');await reorder('tabs-settings',0,'ArrowRight');
  assert.equal(await ui(`document.querySelector('.subtabs [role=tab]').textContent`),'主题与动态');
  assert.ok(await ui(`document.body.innerText.includes('陪伴与启动')`),'active subpage identity changed');
  await reorder('general-companion',0,'ArrowDown');
  assert.equal(await ui(`document.querySelector('[data-sort-scope="general-companion"] .setting-label').textContent`),'拖放即时吸附');
  assert.equal(await ui(`document.querySelector('[data-sort-scope="general-panels"] h2').textContent`),'陪伴与启动');
  // Exercise native drag events; nested handles must not reorder their parent scope.
  await ui(`(()=>{const g=document.querySelector('[data-sort-scope="general-companion"]'),items=g.querySelectorAll(':scope>.sortable-item'),d=new DataTransfer();items[0].querySelector('.sort-grip').dispatchEvent(new DragEvent('dragstart',{bubbles:true,dataTransfer:d}));items[2].dispatchEvent(new DragEvent('dragover',{bubbles:true,cancelable:true,dataTransfer:d}));items[2].dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:d}));})()`);await wait(300);
  assert.equal(await ui(`document.querySelector('[data-sort-scope="general-companion"] .setting-label').textContent`),'显示雪');
  await capture('reorder-settings');
  window.reload();await wait(1200);
  assert.equal(await ui(`document.querySelector('nav button').getAttribute('aria-label')`),'角色');
  await nav('设置');assert.equal(await ui(`document.querySelector('.subtabs [role=tab]').textContent`),'主题与动态');
  assert.equal(await ui(`document.querySelector('[data-sort-scope="general-companion"] .setting-label').textContent`),'显示雪');
  await click('快捷键');await reorder('shortcut-entries',0,'ArrowDown');assert.equal(await ui(`document.querySelector('[data-sort-scope="shortcut-entries"] input').getAttribute('aria-label')`),'显示 / 隐藏雪快捷键');
  await click('人设与记忆');await reorder('memory-entries',0,'ArrowDown');assert.equal(await ui(`document.querySelector('[data-sort-scope="memory-entries"] label').textContent`),'需要长期记住的事');
 });
 await check('header theme picker changes every page and persists to host',async()=>{
  await nav('总览');
  for(const theme of ['light','mist','dark']){
   await ui(`(()=>{const e=document.querySelector('[aria-label="工作台主题"]');e.value=${JSON.stringify(theme)};e.dispatchEvent(new Event('change',{bubbles:true}));})()`);await wait(350);
   assert.equal(await ui('document.documentElement.dataset.theme'),theme);
   assert.equal((await ui('window.yukiHost.workbenchConfig()')).theme,theme);
  }
  await nav('角色');assert.equal(await ui('document.querySelector(".window-theme select").value'),'dark');
 });
 await check('three themes persist to host and compact and expanded layouts fit',async()=>{
  await nav('设置');await click('主题与动态');for(const theme of ['雪白','银雾','星夜']){
   await ui(`document.querySelectorAll('.theme-gallery button')[${['雪白','银雾','星夜'].indexOf(theme)}].click()`);await wait(300);await nav('总览');await capture('overview-'+theme);
   window.setSize(880,640);await wait(180);assert.ok(await ui('document.querySelector("main").scrollWidth<=document.querySelector("main").clientWidth'),'compact content overflow');await capture('compact-'+theme);window.setSize(1180,820);await nav('设置');await click('主题与动态');
  }
  assert.equal((await ui('window.yukiHost.workbenchConfig()')).theme,'dark');
  await ui('window.yukiHost.windowMode(true)');await wait(200);await nav('总览');await capture('wide-dark');await ui('window.yukiHost.windowMode(false)');
 });
 await check('default layout editing works and legacy custom pages are removed',async()=>{
  await nav('总览');const count=await ui('document.querySelectorAll(".workspace-widget").length');
  await click('自定义布局');await click('添加区块');await click('专注计时');assert.equal(await ui('document.querySelectorAll(".workspace-widget").length'),count+1);await click('取消');assert.equal(await ui('document.querySelectorAll(".workspace-widget").length'),count);
  await click('自定义布局');await click('添加区块');await click('专注计时');await capture('layout-edit');await click('完成');
  assert.equal(await ui('JSON.parse(localStorage.getItem("yuki-v2-pages"))[0].widgets.length'),count+1);
  assert.equal(await ui(`document.querySelector('[aria-label="新建自定义页面"]')===null`),true);
  await ui(`localStorage.setItem('yuki-v2-pages',JSON.stringify([...JSON.parse(localStorage.getItem('yuki-v2-pages')),{id:'legacy-custom',name:'旧页面',widgets:[]} ]));localStorage.setItem('yuki-v2-start-page',JSON.stringify('legacy-custom'))`);
  window.reload();await wait(1200);
  assert.equal(await ui('JSON.parse(localStorage.getItem("yuki-v2-pages")).length'),1);
  assert.equal(await ui('JSON.parse(localStorage.getItem("yuki-v2-pages"))[0].id'),'default');
 });
 await check('todo creation, completion and removal persist with Unicode text',async()=>{
  await nav('工具');await click('待办事项');await field('待办事项','为雪准备一杯茶');await click('添加');assert.ok(await ui('document.querySelector(".todo-list").textContent.includes("为雪准备一杯茶")'));
  await ui(`document.querySelector('[aria-label="完成 为雪准备一杯茶"]').click()`);await wait(100);assert.equal(await ui('JSON.parse(localStorage.getItem("yuki-v2-todos"))[0].done'),true);
  await ui(`document.querySelector('[aria-label="删除 为雪准备一杯茶"]').click()`);
 });
 await check('focus preserves saved pet preferences and ends cleanly',async()=>{
  const before=(await sidecar.request('get_state')).state.preferences.quiet;
  await nav('工具');await click('时间管理');await click('开始');await wait(250);
  assert.equal((await sidecar.request('get_state')).state.preferences.quiet,before);assert.equal(await ui('document.documentElement.dataset.focus'),'true');
  await click('暂停');await wait(250);assert.equal(await ui('document.documentElement.dataset.focus'),'false');
 });
 await check('memory, shortcuts and invalid IPC validation are real',async()=>{
  const c=await ui('window.yukiHost.workbenchConfig()');const result=await ui(`window.yukiHost.workbenchSet({memory:'喜欢安静的华尔兹'})`);assert.equal(result.memory,'喜欢安静的华尔兹');
  await assert.rejects(ui(`window.yukiHost.workbenchSet({theme:'invalid'})`));await assert.rejects(ui(`window.yukiHost.windowMode('wide')`));
  await ui(`window.yukiHost.workbenchSet({memory:${JSON.stringify(c.memory)}})`);
 });
 await check('navigation and timers survive renderer reload',async()=>{
  window.reload();await wait(1200);assert.ok(await ui('document.body.innerText.includes("默认总览")'));
  assert.equal(await ui('document.documentElement.dataset.theme'),'dark');await nav('总览');await capture('final-overview');
 });
 assert.deepEqual(errors,[]);await sidecar.stop();assert.equal(sidecar.child,null);results.push('backend exits cleanly');
 const report={passed:results.length,results,errors,durationMs:Date.now()-started};if(process.env.YUKI_SMOKE_REPORT){fs.mkdirSync(path.dirname(process.env.YUKI_SMOKE_REPORT),{recursive:true});fs.writeFileSync(process.env.YUKI_SMOKE_REPORT,JSON.stringify(report,null,2));}console.log(JSON.stringify(report));await stopAndQuit();
}
module.exports={run};
