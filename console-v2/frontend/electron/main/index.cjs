'use strict';
const {app,BrowserWindow,Tray,Menu,Notification,ipcMain,protocol,session,dialog,nativeImage,nativeTheme,clipboard,powerMonitor,safeStorage,screen,desktopCapturer,globalShortcut,shell}=require('electron');
const path=require('node:path');
const fs=require('node:fs');
const {spawn}=require('node:child_process');
const smoke=process.argv.includes('--smoke-test');
const updateReadyFile=process.env.YUKI_UPDATE_READY_FILE;
delete process.env.YUKI_UPDATE_READY_FILE;
app.setName('yuki');
if(process.env.YUKI_USER_DATA)app.setPath('userData',path.resolve(process.env.YUKI_USER_DATA));
const {createMainLogger}=require('./logging.cjs');
const logger=createMainLogger({file:path.join(app.getPath('logs'),'yuki.log'),mirror:smoke});
global.console=logger.console;
const log=logger.log;
const {Updater}=require('./updater.cjs');
const {Sidecar}=require('./sidecar.cjs');
const {CSP,resourcePath,trusted,webPreferences,harden,closeBehavior}=require('./security.cjs');
const {validate}=require('../shared/protocol.cjs');
const {Assistant}=require('./assistant.cjs');
const assistant=new Assistant();
assistant.imagePreview=data=>{try{const image=nativeImage.createFromDataURL(data);return image.isEmpty()?undefined:image.resize({width:240,quality:'good'}).toDataURL();}catch{return undefined;}};
const {DesktopServices}=require('./desktop-services.cjs');
const {ModelConfig}=require('./model-config.cjs');
const {Conversations}=require('./conversations.cjs');
const {coalesceUpdates}=require('./stream-coalesce.cjs');
const {discoverLocalServices}=require('./local-services.cjs');
const {LocalModel,ENDPOINT:LOCAL_ENDPOINT,MODEL:LOCAL_MODEL}=require('./local-model.cjs');
let localModel;
const {QuickChat}=require('./quick-chat.cjs');
const quickChat=new QuickChat(assistant, payload=>sidecar.request('speech_update',payload));

protocol.registerSchemesAsPrivileged([{scheme:'yuki',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
const ownsLock=app.requestSingleInstanceLock();
let window=null,tray=null,sidecar=null,quitting=false,exitWork=null,started=false,startFallback=null,notificationWindow=null,notificationReady=null,notificationTimer=null,timers=null;
let runtimeRoot,uiRoot;
let desktopServices,modelConfig,workbenchConfig,quickTools,conversations;
let updater;
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
let avatarIconState='frozen',desktopShortcutWork=Promise.resolve();
function translationMode(enabled){const result=translation.setEnabled(enabled);if(!enabled){translationWindows.dismiss();translationWindows.closeOverlay();}refreshTray();if(workbenchConfig)void syncWorkbench();return result;}
function startTranslationCapture(){return translationWindows.capture().catch(error=>{translation.update({error:String(error.message||error)});});}
function showConsole(){if(window&&!window.isDestroyed()){if(window.isMinimized())window.restore();window.show();window.focus();setAvatarIconState('active');}}
function workbenchVisible(){return !!(window&&!window.isDestroyed()&&window.isVisible()&&!window.isMinimized());}
function send(channel,value){if(window&&!window.isDestroyed())window.webContents.send(channel,value);}
function guard(event){if(!trusted(event,window))throw new Error('拒绝未知页面的桌面请求');}
async function showDesktopNotification(text){
  const body=String(text||'').trim();if(!body)return;
  if(!notificationWindow||notificationWindow.isDestroyed()){
    notificationWindow=new BrowserWindow({width:440,height:148,show:false,frame:false,transparent:true,resizable:false,movable:false,focusable:true,alwaysOnTop:true,skipTaskbar:true,hasShadow:false,backgroundColor:'#00000000',webPreferences:webPreferences(path.join(__dirname,'../preload/notification.cjs'))});
    harden(notificationWindow);notificationWindow.setMenuBarVisibility(false);notificationWindow.setAlwaysOnTop(true,'floating');notificationWindow.on('closed',()=>{notificationWindow=null;notificationReady=null;});
    notificationReady=notificationWindow.loadURL('yuki://app/notification.html');await notificationReady;
  }else if(notificationReady)await notificationReady;
  if(!notificationWindow||notificationWindow.isDestroyed())return;
  const area=screen.getPrimaryDisplay().workArea;const [width,height]=notificationWindow.getSize();
  notificationWindow.setPosition(Math.round(area.x+area.width-width-22),Math.round(area.y+area.height-height-22));
  notificationWindow.webContents.send('yuki:notification-update',{title:'yuki · 小提醒',text:body,theme:workbenchConfig?.value?.theme||'mist',kind:'reminder'});
  notificationWindow.showInactive();notificationWindow.setAlwaysOnTop(true,'floating');
  clearTimeout(notificationTimer);notificationTimer=setTimeout(()=>{if(notificationWindow&&!notificationWindow.isDestroyed())notificationWindow.hide();},7200);
}
// The self-drawn card is the primary path; the system notification is only the fallback.
// Every delivery is recorded so the smoke run can prove a reminder reached the desktop while
// the workbench window was hidden.
const desktopReminders=[];
function notifyDesktop(text){
  void showDesktopNotification(text).then(()=>{
    desktopReminders.push({text,at:Date.now(),shown:!!(notificationWindow&&!notificationWindow.isDestroyed()&&notificationWindow.isVisible())});
    if(desktopReminders.length>20)desktopReminders.shift();
  }).catch(error=>{log(`自绘桌面提醒失败：${error.message||error}`);if(Notification.isSupported())new Notification({title:'Yuki · 小提醒',body:text,silent:true}).show();});
}
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
  updater?.stop();
  clearTimeout(startFallback);startFallback=null;
  assistant.cancel();
  quickChat.cancel();
  exitWork=(async()=>{
    await waitForExitAnimation();setAvatarIconState('frozen');await desktopShortcutWork;globalShortcut.unregisterAll();
    clearTimeout(notificationTimer);notificationWindow?.destroy();notificationWindow=null;
    timers?.stop();translation?.stop();translationWindows?.stop();desktopServices?.stop();
    const results=await Promise.allSettled([sidecar?.stop(),localModel?.stop()]);
    for(const result of results)if(result.status==='rejected')log(result.reason);
    tray?.destroy();tray=null;
    await conversations?.flush();
    app.quit();
  })();
  return exitWork;
}
function configureIpc(){
  ipcMain.handle('yuki:update-status',event=>{guard(event);return updater.snapshot();});
  ipcMain.handle('yuki:update-check',event=>{guard(event);return updater.check();});
  ipcMain.handle('yuki:update-download',event=>{guard(event);return updater.download();});
  ipcMain.handle('yuki:update-install',event=>{guard(event);return updater.install();});
  ipcMain.handle('yuki:notification-close',event=>{if(notificationWindow&&!notificationWindow.isDestroyed()&&event.sender===notificationWindow.webContents){notificationWindow.hide();clearTimeout(notificationTimer);}});
  ipcMain.handle('yuki:open-external',(event,url)=>{guard(event);const parsed=new URL(String(url));if(parsed.protocol!=='https:')throw new Error('只允许打开 HTTPS 来源');return shell.openExternal(parsed.href);});
  ipcMain.handle('yuki:workbench-config',event=>{guard(event);return {...workbenchConfig.snapshot(),shortcutStatus:{...registeredShortcuts}};});
  ipcMain.handle('yuki:workbench-set',async(event,input)=>{guard(event);const next=workbenchConfig.validate(input),previous=workbenchConfig.snapshot();if(input.shortcuts)installShortcuts(next.shortcuts);try{workbenchConfig.write(next);}catch(e){if(input.shortcuts)installShortcuts(previous.shortcuts);throw e;}await syncWorkbench();refreshTray();return {...workbenchConfig.snapshot(),shortcutStatus:{...registeredShortcuts}};});
  ipcMain.handle('yuki:window-mode',(event,wide,animate=false)=>{guard(event);if(typeof wide!=='boolean'||typeof animate!=='boolean')throw Error('窗口模式无效');return require('./workbench-window.cjs').setWindowMode(window,screen,wide,animate);});
  ipcMain.handle('yuki:workbench-visibility',event=>{guard(event);return workbenchVisible();});
  ipcMain.handle('yuki:translation-mode',(event,value)=>{guard(event);return value===undefined?translation.snapshot():translationMode(value);});
  ipcMain.handle('yuki:translation-capture',event=>{guard(event);return startTranslationCapture();});
  ipcMain.handle('yuki:quick-tools-sync',async(event,value)=>{guard(event);await quickTools.sync(value);});
  ipcMain.handle('yuki:desktop-snapshot',event=>{guard(event);return desktopServices.snapshot();});
  ipcMain.handle('yuki:desktop-action',async(event,input)=>{
    guard(event);
    return desktopServices.action(input);
  });
  // Clipboard bodies stay in the main process; the detail pane asks for one by id.
  ipcMain.handle('yuki:clipboard-read',(event,id)=>{guard(event);return desktopServices.clipboardBody(id);});
  ipcMain.handle('yuki:workbench-timers',event=>{guard(event);return timers.snapshot();});
  ipcMain.handle('yuki:workbench-timers-set',(event,input,onlyIfPristine=false)=>{
    guard(event);
    if(typeof onlyIfPristine!=='boolean')throw Error('计时状态无效');
    // The legacy renderer cache may arrive after the native menu made an edit.
    if(onlyIfPristine){
      const current=timers.snapshot();
      if(current.todos.length||current.focus.completed||current.focus.end||current.health.enabled)return current;
    }
    const value=timers.apply(input);
    timers.changed(value);
    return value;
  });
  ipcMain.handle('yuki:workbench-todo-change',(event,change)=>{guard(event);return timers.changeTodo(change);});
  let builtinChanging=false;
  ipcMain.handle('yuki:builtin-model-set',async(event,enabled)=>{
    guard(event);
    if(typeof enabled!=='boolean')throw Error('内置模型开关无效');
    if(builtinChanging)throw Error('内置模型正在切换，请稍候');
    builtinChanging=true;
    try{
      await modelConfig.setBuiltinEnabled(enabled);
      if(!enabled){
        if(modelConfig.value.endpoint===LOCAL_ENDPOINT){assistant.cancel();quickChat.cancel();translation?.cancel();}
        await localModel.stop();
      }else{
        try{await localModel.resume();}catch(error){await modelConfig.setBuiltinEnabled(false);await localModel.stop();throw error;}
      }
      return modelConfig.snapshot();
    }finally{builtinChanging=false;}
  });
  ipcMain.handle('yuki:model-config',async event=>{guard(event);await modelConfig.ready;return modelConfig.snapshot();});
  ipcMain.handle('yuki:model-config-set',async(event,input)=>{guard(event);if(assistant.active||quickChat.busy)throw new Error('请等待当前对话结束后再更改模型');translation?.cancel();const result=await modelConfig.set(input);assistant.configure(modelConfig);return result;});
  ipcMain.handle('yuki:model-test',async(event,input)=>{guard(event);return modelConfig.test(input);});
  ipcMain.handle('yuki:translation-config',async event=>{guard(event);await modelConfig.ready;return modelConfig.snapshot().translation;});
  ipcMain.handle('yuki:translation-config-set',async(event,input)=>{guard(event);translation?.cancel();return (await modelConfig.setTranslation(input)).translation;});
  ipcMain.handle('yuki:model-profile-save',async(event,input)=>{guard(event);if(assistant.active||quickChat.busy)throw new Error('请等待当前对话结束后再更改模型');return modelConfig.saveProfile(input);});
  ipcMain.handle('yuki:model-profile-use',async(event,id)=>{guard(event);if(assistant.active||quickChat.busy)throw new Error('请等待当前对话结束后再更改模型');translation?.cancel();const result=await modelConfig.useProfile(id);assistant.configure(modelConfig);return result;});
  ipcMain.handle('yuki:model-profile-delete',async(event,id)=>{guard(event);return modelConfig.deleteProfile(id);});
  // Toggling this must not cancel a running reply, so the flag is pushed directly instead of re-configuring.
  ipcMain.handle('yuki:model-attachments-set',async(event,enabled)=>{guard(event);const result=await modelConfig.setRemoteAttachments(enabled===true);assistant.allowRemoteAttachments=modelConfig.allowRemoteAttachments;assistant.attachmentReviews.clear();assistant.attachmentApprovals.clear();return result;});
  // Loopback probe only: it never reaches a remote host, so it stays outside the model config.
  ipcMain.handle('yuki:model-discover',async event=>{guard(event);await modelConfig.ready;return discoverLocalServices({current:modelConfig.value.endpoint,builtinEnabled:modelConfig.builtinEnabled});});
  ipcMain.handle('yuki:ai-attach-mode',(event,input)=>{guard(event);if(!input||typeof input!=='object'||Array.isArray(input))throw Error('附件参数无效');const {id,mode}=input;return assistant.attachments.setMode(id,String(mode));});
  ipcMain.handle('yuki:ai-attachment-review',(event,input)=>{guard(event);if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(key=>!['ids','model'].includes(key)))throw Error('附件检查参数无效');return assistant.reviewAttachments(input.ids,input.model);});
  ipcMain.handle('yuki:ai-attachment-approve',async(event,input)=>{guard(event);if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(key=>!['reviewId','ids','model'].includes(key)))throw Error('附件确认参数无效');const review=assistant.validateAttachmentReview(input);if(!['localhost','127.0.0.1','[::1]'].includes(new URL(review.endpoint).hostname)&&!assistant.allowRemoteAttachments)throw Error('请先为此云端服务开启附件授权');if(['localhost','127.0.0.1','[::1]'].includes(new URL(review.endpoint).hostname))return {ticket:''};const result=await dialog.showMessageBox(window,{type:'warning',title:'确认发送附件到云端',message:`将 ${review.items.length} 个附件发送到 ${review.endpointHost}？`,detail:`模型：${review.model}\n图片会按需缩小至最长边 1536 px；已提取的 OCR/文档文字也会随对话发送。\n返回前端可逐项检查或移除附件。`,buttons:['返回检查','发送附件'],defaultId:0,cancelId:0});if(result.response!==1)throw Error('已取消云端附件发送；附件仍保留在输入框。');return assistant.approveAttachments(input,review.endpoint);});
  ipcMain.handle('yuki:conversations',event=>{guard(event);return conversations.snapshot();});
  ipcMain.handle('yuki:conversation-store',(event,input)=>{guard(event);if(!input||typeof input!=='object'||Array.isArray(input))throw Error('这段对话已达到本机保存上限，请新建对话后继续。');return conversations.store(input.id,input.messages,input);});
  ipcMain.handle('yuki:conversation-new',event=>{guard(event);return conversations.create();});
  ipcMain.handle('yuki:conversation-open',(event,id)=>{guard(event);return conversations.open(id);});
  ipcMain.handle('yuki:conversation-rename',(event,input)=>{guard(event);if(!input||typeof input!=='object'||Array.isArray(input))throw Error('会话参数无效');return conversations.rename(input.id,input.title);});
  ipcMain.handle('yuki:conversation-delete',(event,id)=>{guard(event);return conversations.remove(id);});
  ipcMain.handle('yuki:conversations-clear',event=>{guard(event);return conversations.clear();});
  ipcMain.handle('yuki:conversations-persistence',(event,enabled)=>{guard(event);return conversations.setPersistence(enabled===true);});
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
    let result;const stream=coalesceUpdates(value=>send('yuki:ai-update',value));
    try{result=await assistant.chat(payload,value=>stream.push(value));}
    catch(error){
      if(sidecar?.ready&&!/回复已停止|等待超时/.test(String(error?.message||error)))await sidecar.request('desktop_event',{kind:'error',text:'这次回复没有完成'}).catch(log);
      throw error;
    }
    finally{stream.flush();}
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
    tray=new Tray(iconPathForState('frozen'));
    tray.setToolTip('yuki · 桌面小屋');
    refreshTray();
    tray.on('click',showConsole);tray.on('double-click',showConsole);
  }catch(error){log(`托盘不可用：${error.message}`);tray=null;}
}
function iconPathForState(state){
 const stem=state==='frozen'?'yuki-desktop-frozen-block-v10':'yuki-desktop-active-neat-v8';
 return path.join(__dirname,`../icons/${stem}.ico`);
}
function refreshAvatarIcons(){setAvatarIconState(avatarIconState);}
function updateDesktopShortcutIcon(state){
 if(process.platform!=='win32'||!app.isPackaged)return Promise.resolve(false);
 const helper=path.join(__dirname,'desktop-shortcut-icon.ps1');
 const iconPath=iconPathForState(state);
 const run=()=>new Promise(resolve=>{
  const powershell=path.join(process.env.SystemRoot||'C:\\Windows','System32','WindowsPowerShell','v1.0','powershell.exe');
  const child=spawn(powershell,['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',helper,'-TargetExe',process.execPath,'-IconPath',iconPath],{windowsHide:true,stdio:'ignore'});
  child.once('error',error=>{log(`更新桌面快捷方式图标失败：${error.message}`);resolve(false);});
  child.once('close',code=>{if(code!==0)log(`更新桌面快捷方式图标失败，退出代码 ${code}`);resolve(code===0);});
 });
 desktopShortcutWork=desktopShortcutWork.then(run,run);
 return desktopShortcutWork;
}
function setAvatarIconState(state){
 avatarIconState=state;
 const image=nativeImage.createFromPath(iconPathForState(state));
 if(!image.isEmpty()){
  if(tray&&!tray.isDestroyed())tray.setImage(image);
  if(window&&!window.isDestroyed())window.setIcon(image);
 }
 void updateDesktopShortcutIcon(state);
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
    icon:iconPathForState('frozen'),
    show:false,backgroundColor:'#E8EEF3',webPreferences:{...webPreferences(path.join(__dirname,'../preload/console.cjs')),backgroundThrottling:false}});
  harden(window);window.setMenuBarVisibility(false);
  let visible=workbenchVisible();
  for(const event of ['show','hide','minimize','restore'])window.on(event,()=>{
    const next=workbenchVisible();
    if(next!==visible){visible=next;send('yuki:workbench-visibility',next);}
  });
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
    await updateDesktopShortcutIcon('frozen');
    nativeTheme.on('updated',refreshAvatarIcons);
    updater=new Updater({
      app, log, enabled:app.isPackaged && process.platform==='win32' && process.arch==='x64' && !smoke,
      changed:value=>send('yuki:update-status',value), quit:()=>void stopAndQuit(),
    });
    sidecar=new Sidecar(backendOptions());
    modelConfig=new ModelConfig(path.join(app.getPath('userData'),'model.json'),safeStorage);
    await modelConfig.ready;
    localModel=new LocalModel({root:app.isPackaged?path.join(process.resourcesPath,'local-model/qwen'):path.resolve(__dirname,'../../../../local-model/qwen'),log});
    // Adopt the bundled model for the old default local connection; retain explicitly selected services.
    // Only when the built-in is switched on: otherwise a fresh install lands on a disabled endpoint
    // while a perfectly good LM Studio is listening on the default port.
    if(modelConfig.builtinEnabled&&localModel.available&&!modelConfig.key&&['http://127.0.0.1:1235/v1','http://127.0.0.1:1234/v1'].includes(modelConfig.value.endpoint)&&(!modelConfig.value.model||modelConfig.value.model===LOCAL_MODEL))await modelConfig.set({endpoint:LOCAL_ENDPOINT,model:LOCAL_MODEL});
    modelConfig.ensureReady=endpoint=>endpoint===LOCAL_ENDPOINT?(modelConfig.builtinEnabled?localModel.ensure():Promise.reject(Error('内置模型已关闭，请在设置 → 通用中开启，或切换云端 API。'))):Promise.resolve();
    if(modelConfig.builtinEnabled&&modelConfig.value.endpoint===LOCAL_ENDPOINT)void localModel.ensure().catch(error=>log('本地 Qwen：'+error.message));
    const {WorkbenchConfig}=require('./workbench-config.cjs');workbenchConfig=new WorkbenchConfig(path.join(app.getPath('userData'),'workbench.json'));
    conversations=await Conversations.loadAsync(path.join(app.getPath('userData'),'conversations.json'),{log});
    if(!conversations.sessions.length)await conversations.create();
    assistant.configure(modelConfig);
    desktopServices=new DesktopServices({app,clipboard,powerMonitor,log,react:async entry=>{
      send('yuki:desktop-event',entry);
      if(sidecar?.ready)await sidecar.request('desktop_event',{kind:entry.kind,text:entry.text});
    }});
    // Only a signal goes out: the renderer pulls a snapshot when it is actually looking,
    // and nothing is produced at all while the workbench is hidden.
    desktopServices.onChanged=()=>{if(workbenchVisible())send('yuki:desktop-changed',{at:Date.now()});};
    const {QuickTools}=require('./quick-tools.cjs');
    quickTools=new QuickTools({desktop:desktopServices,deliver:payload=>sidecar.ready?sidecar.request('quick_tools_update',payload):Promise.resolve(),forward:value=>send('yuki:quick-tool',value),timers:()=>timers});
    desktopServices.notify=notifyDesktop;
    const {WorkbenchTimers}=require('./workbench-timers.cjs');
    // Focus, todos and health reminders are scheduled here rather than in the page, so closing
    // the workbench no longer stops the clock.
    timers=new WorkbenchTimers({file:path.join(app.getPath('userData'),'workbench-timers.json'),notify:notifyDesktop,powerMonitor,log,
      changed:(value=timers.snapshot())=>{
        send('yuki:workbench-timers',value);
        if(timers&&sidecar?.ready)void quickTools.publish().catch(log);
      }});
    timers.start();
    const {Translation}=require('./translation.cjs');
    const {TranslationWindows}=require('./translation-windows.cjs');
    const {LocalOCR}=require('./ocr.cjs');
    translation=new Translation({config:modelConfig,exclude:()=>sidecar.child?[sidecar.child.pid]:[],
      suppressClipboard:ms=>{desktopServices.clipboardSuppressedUntil=Date.now()+ms;},
      display:point=>{void translationWindows.show(point).catch(()=>translation.update({phase:'error',error:'无法打开翻译浮窗，请重启 Yuki。'}));},
      changed:value=>{send('yuki:translation-state',value);translationWindows?.update(value);if(value.enabled!==translationTrayEnabled){translationTrayEnabled=value.enabled;refreshTray();}if(!value.enabled){translationWindows?.dismiss();translationWindows?.closeOverlay();}}});
    translationWindows=new TranslationWindows({BrowserWindow,screen,desktopCapturer,ipcMain,nativeImage,clipboard,translation,ocr:new LocalOCR()});
    sidecar.on('message',message=>{if('frame' in message)return;send('yuki:message',message);
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
    void updater.start(updateReadyFile).catch(error=>log('初始化 Yuki 更新：'+error.message));
    if(smoke)await require(process.env.YUKI_WORKBENCH_SMOKE==='1'?'./workbench-smoke.cjs':process.env.YUKI_AI_SMOKE==='1'?'./ai-smoke.cjs':process.env.YUKI_TIMERS_SMOKE==='1'?'./timers-smoke.cjs':'./smoke.cjs').run({app,window,sidecar,tray,stopAndQuit,log,translation,translationWindows,quickTools,timers,desktopReminders,notifyWindow:()=>notificationWindow});
  }).catch(async error=>{log(error.stack||error.message);
    if(smoke){console.error(error);process.exitCode=1;await sidecar?.stop();app.exit(1);}
    else {dialog.showErrorBox('yuki 启动失败',error.message);await stopAndQuit();}
  });
}
