'use strict';
const {app,BrowserWindow,protocol,screen}=require('electron');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {resourcePath,CSP}=require('../console-v2/frontend/electron/main/security.cjs');
const {setWindowMode}=require('../console-v2/frontend/electron/main/workbench-window.cjs');
const out=path.resolve(__dirname,'../work/workbench-window-qa'+(process.argv.includes('--interaction-only')?'-interaction':'' ));
app.setPath('userData',path.join(out,'profile'));
protocol.registerSchemesAsPrivileged([{scheme:'yuki',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
const delay=ms=>new Promise(r=>setTimeout(r,ms));
app.whenReady().then(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const root=path.resolve(__dirname,'../console-v2/frontend/dist');
 protocol.handle('yuki',async req=>{const file=resourcePath(req.url,root);try{return new Response(await fs.promises.readFile(file),{headers:{'Content-Type':{'.html':'text/html','.js':'text/javascript','.css':'text/css','.webp':'image/webp','.png':'image/png'}[path.extname(file)]||'application/octet-stream','Content-Security-Policy':CSP}});}catch{return new Response('',{status:404});}});
 const win=new BrowserWindow({width:900,height:740,minWidth:520,minHeight:420,show:process.argv.includes('--interactive'),webPreferences:{sandbox:true,contextIsolation:true,backgroundThrottling:false,offscreen:!process.argv.includes('--interactive')}});
 const errors=[];win.webContents.on('console-message',(_e,...args)=>{if(args[0]===3)errors.push(args[1]);});
 await win.loadURL('yuki://app/index.html?demo=1');await delay(500);
 const ui=code=>win.webContents.executeJavaScript(code);
 const capture=async name=>fs.writeFileSync(path.join(out,name+'.png'),(await win.webContents.capturePage()).toPNG());
 const click=async selector=>{await ui(`document.querySelector(${JSON.stringify(selector)})?.click()`);await ui(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);await delay(340);};
 const results=[];
 const flush=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({results,errors},null,2));
 // Legacy saved boards must discard the retired player without losing other widgets.
 await ui(`localStorage.setItem('yuki-v2-pages',JSON.stringify([{id:'default',name:'默认总览',widgets:[{id:'old-player',type:'media',title:'正在聆听',width:1,height:260},{id:'kept',type:'system',title:'保留我的电脑状态',width:2,height:300}]}]))`);
 await win.reload();await delay(350);
 assert.equal(await ui(`!!document.querySelector('.widget-media,.media-v2')`),false);
 assert.ok(await ui(`document.querySelector('.widget-system').textContent.includes('保留我的电脑状态')`));
 assert.equal(await ui(`JSON.parse(localStorage.getItem('yuki-v2-pages'))[0].widgets.some(w=>w.type==='media')`),false);
 await ui(`localStorage.removeItem('yuki-v2-pages')`);await win.reload();await delay(350);
 assert.equal(await ui(`document.querySelectorAll('[data-widget]').length`),4);
 for(const [width,height] of (process.argv.includes('--interaction-only')?[]:[[1600,950],[1180,820],[900,740],[780,600],[520,420]])){
  win.setSize(width,height);await delay(180);if((width>=1180)!==await ui(`document.querySelector('.observatory').classList.contains('is-wide')`))await click('.window-size');
  for(const section of ['总览','角色','AI 助手','工具','设置']){
   await click(`nav button[aria-label="${section}"]`);
   if(section==='character'){
    assert.ok(await ui(`document.querySelector('.subtabs').textContent.includes('随音乐舞动')`));
    assert.ok(await ui(`!!document.querySelector('.music-listening')`));
    assert.equal(await ui(`!!document.querySelector('.media-v2,.media-seek,.lyrics-section')`),false);
   }
   const count=await ui(`document.querySelectorAll('.subtabs [role=tab]').length`);
   for(let tab=0;tab<Math.max(count,1);tab++){
    if(count)await click(`.subtabs .sortable-item:nth-child(${tab+1}) button`);
    const metric=await ui(`(()=>{const main=document.querySelector('main'),r=main.getBoundingClientRect();return {width:innerWidth,height:innerHeight,section:${JSON.stringify(section)},tab:${tab},overflow:main.scrollWidth-main.clientWidth,offenders:[...main.querySelectorAll('*')].filter(e=>{const s=getComputedStyle(e),b=e.getBoundingClientRect();return s.position!=='fixed'&&e.getClientRects().length&&b.width>0&&b.right>r.right+1&&!e.closest('.subtabs')}).slice(0,12).map(e=>({tag:e.tagName,cls:e.className,right:Math.round(e.getBoundingClientRect().right)}))};})()`);
    results.push(metric);flush();
    if(tab===0&&(section==='总览'||section==='设置'))await capture(`${width}-${section}`);
   }
  }
 }
 win.setSize(900,740);await click('nav button[aria-label="总览"]');
 for(const theme of ['雪白','银雾','星夜']){await click('.theme-trigger');await ui(`[...document.querySelectorAll('.theme-options button')].find(b=>b.textContent.includes(${JSON.stringify(theme)})).click()`);await delay(350);await capture('theme-'+theme);}
 await click('.theme-trigger');await delay(400);await capture('theme-picker');
 await ui(`document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',bubbles:true}))`);
 assert.equal(await ui(`!!document.querySelector('.theme-popover')`),false);
 assert.equal(await ui(`document.activeElement.className`),'theme-trigger');
 await win.reload();await delay(350);assert.equal(await ui(`document.documentElement.dataset.theme`),'dark');
 const before=win.getBounds();setWindowMode(win,screen,true);assert.ok(win.isResizable()&&win.isMovable());
 win.setSize(1100,720);await delay(100);const expanded=win.getBounds();setWindowMode(win,screen,false);await delay(100);assert.ok(Math.abs(win.getBounds().width-before.width)<=2);setWindowMode(win,screen,true);await delay(100);assert.ok(Math.abs(win.getBounds().width-expanded.width)<=2);
 fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({results,errors},null,2));
 console.log(JSON.stringify({pages:results.length,overflow:results.filter(x=>x.overflow>1),errors}));assert.equal(results.filter(x=>x.overflow>1).length,0);assert.equal(errors.length,0);
 if(process.argv.includes('--interactive')){win.setSize(900,740);win.setTitle('Yuki · 工作台适配验收');win.setAlwaysOnTop(true,'screen-saver');win.show();setTimeout(()=>app.quit(),180000);}else{win.destroy();app.quit();}
}).catch(e=>{console.error(e);app.exit(1);});

