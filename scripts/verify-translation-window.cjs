'use strict';
// Run with the project's Electron executable, outside the user's running app.
const {app,BrowserWindow,screen,desktopCapturer,ipcMain,nativeImage,protocol}=require('electron');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {TranslationWindows}=require('../console-v2/frontend/electron/main/translation-windows.cjs');
const {resourcePath,CSP}=require('../console-v2/frontend/electron/main/security.cjs');
const out=path.resolve(__dirname,'../work/translation-window-qa');
app.setPath('userData',path.join(out,'profile'));
protocol.registerSchemesAsPrivileged([{scheme:'yuki',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
const delay=ms=>new Promise(resolve=>setTimeout(resolve,ms));
app.whenReady().then(async()=>{
 fs.mkdirSync(out,{recursive:true});
 const root=path.resolve(__dirname,'../console-v2/frontend/public');
 protocol.handle('yuki',async request=>{
  const file=resourcePath(request.url,root);
  const mime={'.html':'text/html; charset=utf-8','.css':'text/css','.js':'text/javascript'}[path.extname(file)];
  return new Response(await fs.promises.readFile(file),{headers:{'content-type':mime,'Content-Security-Policy':CSP}});
 });
 const state={enabled:true,phase:'done',source:'The translation window can now be moved and resized. '.repeat(20),text:'拖动标题栏，可以把翻译窗口移到方便阅读的位置。\n拉动窗口边缘，译文会自动换行，阅读区随窗口大小调整。\n\n'+('这是一段用于验证长译文排版与滚动的文字，关闭和复制按钮应始终可见。'.repeat(35))+'\nhttps://example.com/'+('long-path-'.repeat(30)),target:'简体中文',method:'selection',error:''};
 const translation={enabled:true,generation:0,state,snapshot:()=>({...state}),cancel(){},retry(){}};
 let copied='';const testClipboard={writeText:async text=>{copied=text;}};
 const windows=new TranslationWindows({BrowserWindow,screen,desktopCapturer,ipcMain,nativeImage,clipboard:testClipboard,translation,ocr:{}});
 await windows.show({x:220,y:160});const popup=windows.popup;popup.setTitle('Yuki · 翻译窗口交互验收');
 const ui=code=>popup.webContents.executeJavaScript(code);
 const capture=async name=>{await delay(180);fs.writeFileSync(path.join(out,name+'.png'),(await popup.webContents.capturePage()).toPNG());};
 const metrics=()=>ui(`(()=>{const area=document.querySelector('.result-area'),header=document.querySelector('header'),footer=document.querySelector('footer'),result=document.getElementById('result');return {width:innerWidth,height:innerHeight,horizontalOverflow:document.documentElement.scrollWidth>innerWidth,areaHeight:area.clientHeight,scrolls:area.scrollHeight>area.clientHeight,footerBottom:footer.getBoundingClientRect().bottom,headerTop:header.getBoundingClientRect().top,fontSize:getComputedStyle(result).fontSize,drag:getComputedStyle(header).getPropertyValue('-webkit-app-region'),closeDrag:getComputedStyle(document.getElementById('close')).getPropertyValue('-webkit-app-region'),text:result.textContent.length};})()`);
 const results=[];
 assert.ok(popup.isResizable());assert.ok(popup.isMovable());
 for(const [width,height] of [[320,240],[420,360],[720,540],[1000,700],[640,240]]){
  popup.setSize(width,height);await delay(350);
  for(let i=0;i<20;i++){const m=await metrics();if(Math.abs(m.width-width)<=2&&Math.abs(m.height-height)<=2)break;await delay(100);}
  const m=await metrics();assert.equal(m.horizontalOverflow,false);assert.ok(m.areaHeight>70);assert.ok(m.footerBottom<=m.height+1);assert.equal(m.headerTop,0);assert.ok(m.scrolls);assert.equal(m.drag,'no-drag');assert.equal(m.closeDrag,'no-drag');results.push(m);
  assert.ok(Math.abs(m.width-width)<=2&&Math.abs(m.height-height)<=2,JSON.stringify(m));
  await capture('window-'+width+'x'+height);
 }
 // Text remains selectable, controls work, and source expansion stays inside the scroll area.
 await ui(`document.getElementById('original').open=true`);assert.equal((await metrics()).horizontalOverflow,false);
 await ui(`window.translation.control('copy')`);assert.equal(copied,state.text);
 Object.assign(state,{phase:'error',error:'模型暂时无法连接，请检查后重试。'});windows.update(state);popup.setSize(320,240);await capture('error-320x240');assert.equal((await metrics()).horizontalOverflow,false);
 Object.assign(state,{phase:'loading',error:'',text:''});windows.update(state);await capture('loading-320x240');
 Object.assign(state,{phase:'done',text:'您的下载已完成。',source:'Your download is complete.'});windows.update(state);await ui(`document.getElementById('original').open=false`);
 popup.setSize(420,360);await capture('short-420x360');
 const before=popup.getSize()[0];
 await ui(`document.getElementById('resize').focus();document.getElementById('resize').dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true}))`);await delay(250);
 assert.equal(popup.getSize()[0],before+16);
 windows.dismiss();await windows.show({x:220,y:160});assert.equal(popup.getSize()[0],before+16);
 popup.setSize(420,360);await delay(200);
 fs.writeFileSync(path.join(out,'layout-results.json'),JSON.stringify(results,null,2));
 // Native gesture events provide evidence separate from programmatic layout checks.
 const gestures=[];
 const record=(name,bounds)=>{gestures.push({name,bounds:bounds||popup.getBounds(),preferred:windows.popupSize});fs.writeFileSync(path.join(out,'gestures.json'),JSON.stringify(gestures,null,2));};
 popup.on('move',()=>record('moved'));popup.on('resize',()=>record('resized'));
 popup.on('hide',()=>{record('hidden');app.quit();});
 if(process.argv.includes('--interactive')){const area=screen.getPrimaryDisplay().workArea;popup.setPosition(area.x+area.width-460,area.y+area.height-420);popup.setAlwaysOnTop(true,'screen-saver');popup.show();popup.focus();record('initial');setTimeout(()=>app.quit(),180000);console.log('READY FOR NATIVE GESTURES');}
 else{windows.stop();app.quit();}
 console.log(JSON.stringify({passed:true,layouts:results.length,output:out}));
}).catch(error=>{console.error(error);app.exit(1);});
