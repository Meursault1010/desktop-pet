'use strict';
const {app,BrowserWindow,Tray,Menu,Notification,ipcMain,protocol,session,dialog,nativeImage,clipboard,powerMonitor,safeStorage,screen,desktopCapturer,globalShortcut}=require('electron');
const path=require('node:path');
const fs=require('node:fs');
const smoke=process.argv.includes('--smoke-test');
const prototype=process.argv.includes('--pet-prototype');
app.setName('yuki');
if(process.env.YUKI_USER_DATA)app.setPath('userData',path.resolve(process.env.YUKI_USER_DATA));
const {createMainLogger}=require('./logging.cjs');
const logger=createMainLogger({file:path.join(app.getPath('logs'),'yuki.log'),mirror:smoke});
global.console=logger.console;
const log=logger.log;
const {Sidecar}=require('./sidecar.cjs');
const {CSP,resourcePath,trusted,webPreferences,harden,closeBehavior}=require('./security.cjs');
const {validate}=require('../shared/protocol.cjs');
const {Assistant}=require('./assistant.cjs');
const assistant=new Assistant();
const {DesktopServices}=require('./desktop-services.cjs');
const {ModelConfig}=require('./model-config.cjs');
const {LocalModel,ENDPOINT:LOCAL_ENDPOINT,MODEL:LOCAL_MODEL}=require('./local-model.cjs');
let localModel;
const {QuickChat}=require('./quick-chat.cjs');
const quickChat=new QuickChat(assistant, payload=>sidecar.request('speech_update',payload));

protocol.registerSchemesAsPrivileged([{scheme:'yuki',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
const ownsLock=app.requestSingleInstanceLock();
let window=null,tray=null,sidecar=null,quitting=false,exitWork=null,started=false,startFallback=null;
let runtimeRoot,uiRoot;
let desktopServices,modelConfig,workbenchConfig,quickTools;
let registeredShortcuts={};
function shortcutAction(id){return {console:showConsole,visibility:()=>void sidecar.request('toggle_visibility',{}).catch(log),translation:()=>{try{translationMode(!translation.enabled);}catch(e){translation.update({error:String(e.message||e)});}},capture:()=>void startTranslationCapture()}[id];}
function installShortcuts(next){
 const previous={...registeredShortcuts};for(const key of Object.values(previous))globalShortcut.unregister(key);
 const installed=[];
 try{for(const [id,key] of Object.entries(next)){if(!globalShortcut.register(key,shortcutAction(id)))throw Error('快捷键 '+key+' 已被占用或无效');installed.push(key);}registeredShortcuts={...next};}
 catch(e){for(const key of installed)globalShortcut.unregister(key);registeredShortcuts={};for(const [id,key] of Object.entries(previous))if(globalShortcut.register(key,shortcutAction(id)))registeredShortcuts[id]=key;throw e;}
}
async function syncWorkbench(){const c=workbenchConfig.snapshot();assistant.workbenchContext=c.persona+String.fromCharCode(10)+c.memory;if(sidecar?.ready)await sidecar.request('configure_ui',{theme:c.theme,bubble:c.bubble,reduced:c.reduced,translation:!!translation?.enabled}).catch(log);}
let translation,translationWindows,translationTrayEnabled=false;
function translationMode(enabled){const result=translation.setEnabled(enabled);if(!enabled){translationWindows.dismiss();translationWindows.closeOverlay();}refreshTray();if(workbenchConfig)void syncWorkbench();return result;}
function startTranslationCapture(){return translationWindows.capture().catch(error=>{translation.update({error:String(error.message||error)});});}
function showConsole(){if(window&&!window.isDestroyed()){if(window.isMinimized())window.restore();window.show();window.focus();}}
function send(channel,value){if(window&&!window.isDestroyed())window.webContents.send(channel,value);}
function guard(event){if(!trusted(event,window))throw new Error('拒绝未知页面的桌面请求');}
function markStarted(){if(started||quitting)return;started=true;clearTimeout(startFallback);startFallback=null;showConsole();refreshTray();}
function waitForExitAnimation(){
  return new Promise(resolve=>{
    if(!sidecar?.ready)return resolve();
    let done=false;
    const finish=()=>{if(done)return;done=true;clearTimeout(timer);sidecar.off('message',onMessage);resolve();};
    const onMessage=message=>{if(message.type==='event'&&message.name==='exit_complete')finish();};
    const timer=setTimeout(finish,20000);
    sidecar.on('message',onMessage);
    sidecar.request('prepare_exit',{}).catch(finish);
  });
}
async function stopAndQuit(){
  if(exitWork)return exitWork;
  quitting=true;
  clearTimeout(startFallback);startFallback=null;
  assistant.cancel();
  quickChat.cancel();
  exitWork=(async()=>{await waitForExitAnimation();globalShortcut.unregisterAll();translation?.stop();translationWindows?.stop();desktopServices?.stop();await Promise.all([sidecar?.stop(),localModel?.stop()]);tray?.destroy();tray=null;app.quit();})();
  return exitWork;
}
function configureIpc(){
  ipcMain.handle('yuki:workbench-config',event=>{guard(event);return {...workbenchConfig.snapshot(),shortcutStatus:{...registeredShortcuts}};});
  ipcMain.handle('yuki:workbench-set',async(event,input)=>{guard(event);const next=workbenchConfig.validate(input),previous=workbenchConfig.snapshot();if(input.shortcuts)installShortcuts(next.shortcuts);try{workbenchConfig.write(next);}catch(e){if(input.shortcuts)installShortcuts(previous.shortcuts);throw e;}await syncWorkbench();refreshTray();return {...workbenchConfig.snapshot(),shortcutStatus:{...registeredShortcuts}};});
  ipcMain.handle('yuki:window-mode',(event,wide)=>{guard(event);if(typeof wide!=='boolean')throw Error('窗口模式无效');return require('./workbench-window.cjs').setWindowMode(window,screen,wide);});
  ipcMain.handle('yuki:translation-mode',(event,value)=>{guard(event);return value===undefined?translation.snapshot():translationMode(value);});
  ipcMain.handle('yuki:translation-capture',event=>{guard(event);return startTranslationCapture();});
  ipcMain.handle('yuki:quick-tools-sync',async(event,value)=>{guard(event);await quickTools.sync(value);});
  ipcMain.handle('yuki:desktop-snapshot',event=>{guard(event);return desktopServices.snapshot();});
  ipcMain.handle('yuki:desktop-action',async(event,input)=>{
    guard(event);
    return desktopServices.action(input);
  });
  let builtinChanging=false;
  ipcMain.handle('yuki:builtin-model-set',async(event,enabled)=>{
    guard(event);
    if(typeof enabled!=='boolean')throw Error('内置模型开关无效');
    if(builtinChanging)throw Error('内置模型正在切换，请稍候');
    builtinChanging=true;
    try{
      modelConfig.setBuiltinEnabled(enabled);
      if(!enabled){
        if(modelConfig.value.endpoint===LOCAL_ENDPOINT){assistant.cancel();quickChat.cancel();translation?.cancel();}
        await localModel.stop();
      }else{
        try{await localModel.resume();}catch(error){modelConfig.setBuiltinEnabled(false);await localModel.stop();throw error;}
      }
      return modelConfig.snapshot();
    }finally{builtinChanging=false;}
  });
  ipcMain.handle('yuki:model-config',event=>{guard(event);return modelConfig.snapshot();});
  ipcMain.handle('yuki:model-config-set',(event,input)=>{guard(event);if(assistant.active||quickChat.busy)throw new Error('请等待当前对话结束后再更改模型');translation?.cancel();const result=modelConfig.set(input);assistant.configure(modelConfig);return result;});
  ipcMain.handle('yuki:ai-attach',async event=>{guard(event);
    if(assistant.active)throw Error('请等待回复结束后添加附件');
    const result=await dialog.showOpenDialog(window,{title:'添加图片或文档',properties:['openFile','multiSelections'],filters:[{name:'图片与文档',extensions:['png','jpg','jpeg','webp','pdf','docx','txt','md','csv','json','log']}]});
    if(result.canceled)return [];
    if(result.filePaths.length>4)throw Error('每次最多选择 4 个附件');
    const items=[];for(const file of result.filePaths)items.push(await assistant.attachments.add(file,{imageReader:async buffer=>{const image=nativeImage.createFromBuffer(buffer);if(image.isEmpty())throw Error('图片无法解码');const size=image.getSize();if(size.width*size.height>24000000)throw Error('图片不能超过 2400 万像素');const scale=Math.min(1,1536/Math.max(size.width,size.height));return (scale<1?image.resize({width:Math.max(1,Math.round(size.width*scale)),height:Math.max(1,Math.round(size.height*scale)),quality:'best'}):image).toDataURL();}}));return items;
  });
  ipcMain.handle('yuki:ai-models',async event=>{guard(event);return assistant.models();});
  ipcMain.handle('yuki:ai-chat',async(event,payload)=>{guard(event);
    if(quickChat.busy)throw new Error('yuki 正在回复桌面快捷聊天，请稍等');
    if(sidecar?.ready)await sidecar.request('wake_sleep',{});
    if(sidecar?.ready)await sidecar.request('desktop_event',{kind:'thinking',text:'正在准备回复'}).catch(log);
    let result;
    try{result=await assistant.chat(payload,value=>send('yuki:ai-update',value));}
    catch(error){
      if(sidecar?.ready&&!/回复已停止|等待超时/.test(String(error?.message||error)))await sidecar.request('desktop_event',{kind:'error',text:'这次回复没有完成'}).catch(log);
      throw error;
    }
    assistant.preferredModel=payload.model;
    if(sidecar?.ready)await sidecar.request('desktop_event',{kind:'done',text:'回复已准备好'}).catch(log);
    if(sidecar?.ready)await sidecar.request('speech_update',{id:payload.id,phase:'done',text:result.text.slice(0,6000)}).catch(log);
    return result;
  });
  ipcMain.handle('yuki:ai-cancel',async event=>{guard(event);if(!quickChat.busy)assistant.cancel();});
  ipcMain.handle('yuki:request',async(event,name,payload)=>{guard(event);validate(name,payload);
    if(name==='shutdown')throw new Error('请使用保存并退出');
    if(sidecar.starting)await sidecar.starting;
    return sidecar.request(name,payload);
  });
  ipcMain.handle('yuki:reconnect',async event=>{guard(event);await sidecar.start();});
  ipcMain.handle('yuki:exit',async event=>{guard(event);setImmediate(()=>void stopAndQuit());});
}
function createTray(){
  try {
    const icon=nativeImage.createFromPath(path.join(__dirname,'../../src-tauri/icons/icon.ico'));
    // Packaging places a copy beside the host; keep the source-tree fallback.
    const bundled=nativeImage.createFromPath(path.join(__dirname,'../icon.ico'));
    tray=new Tray(!bundled.isEmpty()?bundled:icon);
    tray.setToolTip('yuki · 桌面小屋');
    refreshTray();
    tray.on('click',showConsole);tray.on('double-click',showConsole);
  }catch(error){log(`托盘不可用：${error.message}`);tray=null;}
}
function refreshTray(){
 if(!tray||tray.isDestroyed())return;
 const perform=(name,payload={})=>sidecar.request(name,payload).catch(error=>{log(error);send('yuki:disconnected',error.message);});
 tray.setContextMenu(Menu.buildFromTemplate([
      {label:'打开 yuki 工作台',click:showConsole},
      {label:'显示 / 隐藏 yuki',click:()=>void perform('toggle_visibility')},
      {label:'暂停 / 继续走动',click:()=>void perform('toggle_pause')},
      {type:'separator'},
      {label:'划线翻译 · '+(workbenchConfig?.value.shortcuts.translation||'Control+Alt+T'),type:'checkbox',checked:!!translation?.enabled,click:item=>{try{translationMode(item.checked);}catch(error){translation.update({error:String(error.message||error)});}}},
      {label:'框选文字翻译 · '+(workbenchConfig?.value.shortcuts.capture||'Control+Alt+O'),enabled:!!translation?.enabled,click:()=>void startTranslationCapture()},
      {type:'separator'},{label:'保存并退出 yuki',click:()=>void stopAndQuit()},
    ]));
}
function backendOptions(){
  runtimeRoot=app.isPackaged?path.join(process.resourcesPath,'pet'):path.resolve(__dirname,'../../..');
  if(!fs.existsSync(path.join(runtimeRoot,'pet_backend.py')))throw new Error('找不到完整宠物资源');
  const bundledPython=path.join(runtimeRoot,'python/python.exe');
  const frozen=path.join(runtimeRoot,'python/yuki-backend.exe');
  const useFrozen=app.isPackaged&&fs.existsSync(frozen);
  const command=useFrozen?frozen:process.env.PET_PYTHON||(fs.existsSync(bundledPython)?bundledPython:path.join(runtimeRoot,'.venv/Scripts/python.exe'));
  if(!fs.existsSync(command))throw new Error('未找到 Python 环境。请先运行 install-electron.bat，或设置 PET_PYTHON。');
  const args=useFrozen?[]:['-u','-B',path.join(runtimeRoot,'pet_backend.py')];
  if(process.env.PET_SETTINGS_FILE)args.push('--settings-file',path.resolve(process.env.PET_SETTINGS_FILE));
  return {command,args,cwd:runtimeRoot,env:{PET_CONTROL_PID:String(process.pid),PET_HOST:'electron',
    ...(smoke?{QT_QPA_PLATFORM:'offscreen'}:{})}};
}
async function registerResources(){
  runtimeRoot=app.isPackaged?path.join(process.resourcesPath,'pet'):path.resolve(__dirname,'../../..');
  uiRoot=app.isPackaged?path.join(app.getAppPath(),'dist'):path.resolve(__dirname,'../../dist');
  // The frozen backend carries the only copy of the character assets.
  const petAssets=app.isPackaged?path.join(runtimeRoot,'python/_internal/assets'):path.join(runtimeRoot,'assets');
  protocol.handle('yuki',async request=>{
    try {
      const url=new URL(request.url);
      const target=url.pathname.startsWith('/pet-assets/')
        ?resourcePath('yuki://app/'+url.pathname.slice('/pet-assets/'.length),petAssets)
        :resourcePath(request.url,uiRoot);
      const ext=path.extname(target).toLowerCase();
      const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css',
        '.json':'application/json','.png':'image/png','.webp':'image/webp','.ico':'image/x-icon','.svg':'image/svg+xml','.woff2':'font/woff2'}[ext];
      if(!mime)return new Response('Forbidden',{status:403});
      return new Response(await fs.promises.readFile(target),{headers:{'content-type':mime,'Content-Security-Policy':CSP,'X-Content-Type-Options':'nosniff'}});
    }catch{return new Response('Not found',{status:404});}
  });
  session.defaultSession.setPermissionRequestHandler((_web,_permission,callback)=>callback(false));
  session.defaultSession.setPermissionCheckHandler(()=>false);
  session.defaultSession.webRequest.onBeforeRequest((details,callback)=>callback({cancel:!details.url.startsWith('yuki://app/')&&!details.url.startsWith('data:')}));
}
async function createConsole(){
  window=new BrowserWindow({title:'yuki · 桌面小屋',width:900,height:740,minWidth:520,minHeight:420,resizable:true,movable:true,
    show:false,backgroundColor:'#E8EEF3',webPreferences:{...webPreferences(path.join(__dirname,'../preload/console.cjs')),backgroundThrottling:false}});
  harden(window);window.setMenuBarVisibility(false);
  window.on('close',event=>{const behavior=closeBehavior({quitting,trayReady:!!tray});
    if(behavior!=='close'){event.preventDefault();if(behavior==='hide')window.hide();else window.minimize();}});
  window.webContents.on('render-process-gone',(_event,details)=>{log(`界面进程退出：${details.reason}`);if(!quitting)showConsole();});
  await window.loadURL('yuki://app/index.html');
}
if(!ownsLock){app.quit();}
else {
  app.on('second-instance',showConsole);
  app.on('activate',showConsole);
  app.on('before-quit',event=>{if(!quitting){event.preventDefault();void stopAndQuit();}});
  app.on('window-all-closed',()=>{});
  app.whenReady().then(async()=>{
    await registerResources();
    if(prototype){await require('./prototype.cjs').launch({app,BrowserWindow,uiRoot,smoke});return;}
    sidecar=new Sidecar(backendOptions());
    modelConfig=new ModelConfig(path.join(app.getPath('userData'),'model.json'),safeStorage);
    localModel=new LocalModel({root:app.isPackaged?path.join(process.resourcesPath,'local-model/qwen'):path.resolve(__dirname,'../../../../local-model/qwen'),log});
    // Adopt the bundled model for the old default local connection; retain explicitly selected services.
    if(localModel.available&&!modelConfig.key&&['http://127.0.0.1:1235/v1','http://127.0.0.1:1234/v1'].includes(modelConfig.value.endpoint)&&(!modelConfig.value.model||modelConfig.value.model===LOCAL_MODEL))modelConfig.set({endpoint:LOCAL_ENDPOINT,model:LOCAL_MODEL});
    modelConfig.ensureReady=endpoint=>endpoint===LOCAL_ENDPOINT?(modelConfig.builtinEnabled?localModel.ensure():Promise.reject(Error('内置模型已关闭，请在设置 → 通用中开启，或切换云端 API。'))):Promise.resolve();
    if(modelConfig.builtinEnabled&&modelConfig.value.endpoint===LOCAL_ENDPOINT)void localModel.ensure().catch(error=>log('本地 Qwen：'+error.message));
    const {WorkbenchConfig}=require('./workbench-config.cjs');workbenchConfig=new WorkbenchConfig(path.join(app.getPath('userData'),'workbench.json'));
    assistant.configure(modelConfig);
    desktopServices=new DesktopServices({app,clipboard,powerMonitor,react:async entry=>{
      send('yuki:desktop-event',entry);
      if(sidecar?.ready)await sidecar.request('desktop_event',{kind:entry.kind,text:entry.text});
    }});
    const {QuickTools}=require('./quick-tools.cjs');
    quickTools=new QuickTools({desktop:desktopServices,deliver:payload=>sidecar.ready?sidecar.request('quick_tools_update',payload):Promise.resolve(),forward:value=>send('yuki:quick-tool',value)});
    desktopServices.notify=text=>{if(Notification.isSupported())new Notification({title:'Yuki · 小提醒',body:text,silent:true}).show();};
    const {Translation}=require('./translation.cjs');
    const {TranslationWindows}=require('./translation-windows.cjs');
    const {LocalOCR}=require('./ocr.cjs');
    translation=new Translation({config:modelConfig,exclude:()=>sidecar.child?[sidecar.child.pid]:[],
      suppressClipboard:ms=>{desktopServices.clipboardSuppressedUntil=Date.now()+ms;},
      display:point=>{void translationWindows.show(point).catch(()=>translation.update({phase:'error',error:'无法打开翻译浮窗，请重启 Yuki。'}));},
      changed:value=>{send('yuki:translation-state',value);translationWindows?.update(value);if(value.enabled!==translationTrayEnabled){translationTrayEnabled=value.enabled;refreshTray();}if(!value.enabled){translationWindows?.dismiss();translationWindows?.closeOverlay();}}});
    translationWindows=new TranslationWindows({BrowserWindow,screen,desktopCapturer,ipcMain,nativeImage,clipboard,translation,ocr:new LocalOCR()});
    sidecar.on('message',message=>{send('yuki:message',message);
      if(message.name==='quick_tool')void quickTools.action(message.tool,message.value).catch(log);
      if(message.name==='quick_chat')void quickChat.run(message.id,message.text).catch(log);
      if(message.name==='entered')markStarted();if(message.name==='open_console')showConsole();if(message.name==='exit_app')void stopAndQuit();
      if(message.name==='translation_toggle'){try{translationMode(!translation.enabled);void syncWorkbench();}catch(e){log(e);}}
      if(message.type==='ready'){void syncWorkbench();void quickTools.publish().catch(log);}});
    sidecar.on('disconnected',reason=>{quickChat.cancel();send('yuki:disconnected',reason);if(!quitting)showConsole();});
    sidecar.on('log',log);
    configureIpc();
    createTray();
    await createConsole();
    await sidecar.start();
    startFallback=setTimeout(markStarted,20000);
    desktopServices.start();
    try{installShortcuts(workbenchConfig.value.shortcuts);}catch(e){log(e);translation.update({error:e.message});}
    await syncWorkbench();
    if(smoke)await require(process.env.YUKI_WORKBENCH_SMOKE==='1'?'./workbench-smoke.cjs':'./smoke.cjs').run({app,window,sidecar,tray,stopAndQuit,log,translation,translationWindows,quickTools});
  }).catch(async error=>{log(error.stack||error.message);
    if(smoke){console.error(error);process.exitCode=1;await sidecar?.stop();app.exit(1);}
    else {dialog.showErrorBox('yuki 启动失败',error.message);await stopAndQuit();}
  });
}
