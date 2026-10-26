'use strict';
// Isolated renderer/IPC fixture; never controls a real media session.
const {app,BrowserWindow,protocol,ipcMain,screen}=require('electron');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {resourcePath,CSP}=require('../console-v2/frontend/electron/main/security.cjs');
const out=path.resolve(__dirname,'../work/media-control-qa');
app.setPath('userData',path.join(out,'profile'));
protocol.registerSchemesAsPrivileged([{scheme:'yuki',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
const delay=ms=>new Promise(r=>setTimeout(r,ms));
app.whenReady().then(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const preload=path.join(out,'fixture.cjs');
 fs.writeFileSync(preload,`const {contextBridge,ipcRenderer}=require('electron');contextBridge.exposeInMainWorld('yukiHost',{kind:'electron',desktopSnapshot:()=>ipcRenderer.invoke('fixture:snapshot'),desktopAction:v=>ipcRenderer.invoke('fixture:action',v),subscribe:()=>()=>{}});`);
 const initial={available:true,title:'音乐控制测试 · 本地夹具',artist:'仅用于界面验收',app:'fixture',status:'Playing',position:63,duration:240,controls:{play:true,pause:true,previous:true,next:true,seek:true}};
 let media={...initial},fail=false;const calls=[];
 const {Lyrics}=require('../console-v2/frontend/electron/main/lyrics.cjs');
 const {LyricsWindow}=require('../console-v2/frontend/electron/main/lyrics-window.cjs');
 const lyrics=new Lyrics({directory:path.join(out,'lyrics'),getMedia:()=>media});
 lyrics.set({enabled:true,overlay:false,autoFind:false,opacity:90,palette:'ice',style:'glass',alwaysOnTop:true});
 class HiddenWindow extends BrowserWindow {showInactive(){this.testVisible=true;}isVisible(){return !!this.testVisible;}hide(){this.testVisible=false;super.hide();}}
 const floating=new LyricsWindow({BrowserWindow:HiddenWindow,screen,lyrics,getMedia:()=>media});
 const seed=()=>{lyrics.snapshot();lyrics.store('[00:00]这是界面验收歌词\n[01:00]当前正在播放的测试歌词\n[01:20]随进度同步切换的下一句\n[02:00]结束测试','本地界面测试夹具',lyrics.key);};
 const snapshot=()=>({clipboard:[],clipboardPaused:false,media,lyrics:lyrics.snapshot(),battery:{available:false},events:[],weather:null,city:'',inbox:''});
 ipcMain.handle('fixture:snapshot',snapshot);
 ipcMain.handle('yuki:lyrics-snapshot',()=>({...lyrics.snapshot(),media}));
 ipcMain.handle('yuki:lyrics-hide',()=>lyrics.set({overlay:false}));
 ipcMain.handle('fixture:action',async(_e,input)=>{
  calls.push(input);await delay(150);
  if(fail)throw Error('测试播放器未接受操作');
  if(input.name==='lyrics-settings'){lyrics.set(input.value);return snapshot();}
  if(input.name==='lyrics-find'||input.name==='lyrics-import'){seed();return snapshot();}
  assert.equal(input.name,'media-control');assert.equal(input.value.app,'fixture');
  media={...media,position:input.value.command==='seek'?input.value.position:media.position,status:input.value.command==='pause'?'Paused':'Playing',title:input.value.command==='next'?'下一首测试曲目':input.value.command==='previous'?'上一首测试曲目':media.title};return snapshot();
 });
 const root=path.resolve(__dirname,'../console-v2/frontend/dist');
 protocol.handle('yuki',async req=>{const file=resourcePath(req.url,root);try{return new Response(await fs.promises.readFile(file),{headers:{'Content-Type':{'.html':'text/html','.js':'text/javascript','.css':'text/css','.png':'image/png'}[path.extname(file)]||'application/octet-stream','Content-Security-Policy':CSP}});}catch{return new Response('',{status:404});}});
 const win=new BrowserWindow({width:1180,height:820,show:false,webPreferences:{sandbox:true,contextIsolation:true,offscreen:true,preload}});
 const ui=code=>win.webContents.executeJavaScript(code);
 const reload=async()=>{await win.loadURL('yuki://app/index.html?demo=1');await delay(600);await ui(`document.querySelector('.media-v2').scrollIntoView({block:'center'})`);};
 const click=async label=>{await ui(`document.querySelector('button[aria-label=${JSON.stringify(label)}]').click()`);await delay(350);};
 await reload();
 for(const [label,command] of [['暂停音乐','pause'],['播放音乐','play'],['下一首','next'],['上一首','previous']]){await click(label);assert.equal(calls.at(-1).value.command,command);}
 media={...initial};seed();await reload();
 await ui(`(()=>{const e=document.querySelector('.media-seek');Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,'90');e.dispatchEvent(new Event('input',{bubbles:true}));e.dispatchEvent(new Event('change',{bubbles:true}));})()`);
 await ui(`document.querySelector('.media-seek').dispatchEvent(new PointerEvent('pointerup',{bubbles:true}))`);await delay(350);
 assert.equal(calls.at(-1).value.command,'seek');assert.equal(media.position,90);assert.ok(await ui(`document.querySelector('.current-lyric').textContent.includes('随进度同步')`));
 await ui(`document.querySelector('.lyrics-options').open=true`);
 await ui(`[...document.querySelectorAll('.lyrics-swatch')].find(e=>e.textContent==='浅樱').click()`);await delay(350);assert.equal(lyrics.settings.palette,'rose');
 await click('显示歌词');assert.equal(await ui(`!!document.querySelector('.lyrics-preview')`),false);await click('显示歌词');
 await click('桌面悬浮歌词');await delay(600);assert.ok(floating.ready);assert.ok(floating.window.isAlwaysOnTop());assert.equal(floating.window.isVisible(),true);
 lyrics.set({opacity:55,alwaysOnTop:false,style:'outline'});assert.ok(Math.abs(floating.window.getOpacity()-.55)<.02);assert.equal(floating.window.isAlwaysOnTop(),false);
 await delay(300);assert.ok(await floating.window.webContents.executeJavaScript(`document.querySelector('.overlay-current').textContent.includes('随进度同步')`));
 fs.writeFileSync(path.join(out,'floating-outline.png'),(await floating.window.webContents.capturePage()).toPNG());
 floating.window.close();assert.equal(lyrics.settings.overlay,false);assert.equal(floating.window.isVisible(),false);
 lyrics.set({opacity:90,style:'glass'});await reload();
 await ui(`document.querySelector('.lyrics-options').open=true;document.querySelector('.lyrics-options').scrollIntoView({block:'start'})`);await delay(300);
 const optionMetrics=await ui(`(()=>{const e=document.querySelector('.lyrics-options');return {overflow:e.scrollWidth-e.clientWidth,style:getComputedStyle(e).fontSize};})()`);assert.ok(optionMetrics.overflow<=1);
 fs.writeFileSync(path.join(out,'lyrics-options.png'),(await win.webContents.capturePage()).toPNG());
 await ui(`document.querySelector('.lyrics-options').open=false`);
 const results=[];
 for(const width of [1180,520]){
  win.setSize(width,820);await delay(300);
  await ui(`document.querySelector('.lyrics-options').open=true;document.querySelector('.lyrics-options').scrollIntoView({block:'start'})`);await delay(200);
  assert.ok(await ui(`document.querySelector('.lyrics-options').scrollWidth-document.querySelector('.lyrics-options').clientWidth<=1`));
  fs.writeFileSync(path.join(out,`${width}-lyrics-options.png`),(await win.webContents.capturePage()).toPNG());
  await ui(`document.querySelector('.lyrics-options').open=false`);
  for(const theme of ['light','mist','dark']){
   await ui(`document.documentElement.dataset.theme='${theme}';document.querySelector('.media-v2').scrollIntoView({block:'center'})`);await delay(250);
   const bounds=await ui(`(()=>{const el=document.querySelector('.media-v2'),r=el.getBoundingClientRect();return {x:Math.floor(r.x),y:Math.floor(r.y),width:Math.ceil(r.width),height:Math.ceil(r.height),overflow:el.scrollWidth-el.clientWidth}})()`);
   assert.ok(bounds.overflow<=1);const {overflow,...rect}=bounds;
   fs.writeFileSync(path.join(out,`${width}-${theme}.png`),(await win.webContents.capturePage(rect)).toPNG());results.push({width,theme,overflow});
  }
 }
 media={...initial,controls:{play:true,pause:true,previous:false,next:false}};await reload();
 assert.equal(await ui(`document.querySelector('[aria-label="下一首"]').disabled`),true);
 media={available:false};await reload();assert.equal(await ui(`[...document.querySelectorAll('.media-controls button')].every(b=>b.disabled)`),true);
 media={available:true,title:'网易云兼容识别',artist:'真实状态不可用的测试夹具',app:'netease-uia:1:2',status:'Unknown',position:null,duration:null,controls:{}};await reload();
 assert.ok(await ui(`document.querySelector('.media-times').textContent.includes('已识别歌曲')`));
 assert.ok(await ui(`document.querySelector('.media-feedback').textContent.includes('暂未提供可读取的播放状态')`));
 assert.ok(await ui(`[...document.querySelectorAll('.media-controls button')].every(b=>b.disabled)&&document.querySelector('.media-seek').disabled`));
 fs.writeFileSync(path.join(out,'netease-partial.png'),(await win.webContents.capturePage()).toPNG());
 media={...initial};fail=true;await reload();await click('暂停音乐');assert.ok(await ui(`document.body.textContent.includes('测试播放器未接受操作')`));
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({fixture:true,calls,results,unsupported:true,noSession:true,error:true,seek:true,syncedLyrics:true,visibility:true,palette:true,overlay:{alwaysOnTop:true,opacity:true,hide:true},expandedSettingsWidths:[1180,520]},null,2));
 console.log('Media renderer: transport/seek, synced lyrics, visibility/color, native overlay topmost/opacity/hide, 6 size/theme captures and error states passed.');floating.stop();win.destroy();app.quit();
}).catch(e=>{console.error(e);app.exit(1);});
