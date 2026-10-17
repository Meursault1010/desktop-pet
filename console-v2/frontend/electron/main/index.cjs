'use strict';
const {app,BrowserWindow,Tray,Menu,ipcMain,protocol,session,dialog,nativeImage}=require('electron');
const path=require('node:path');
const fs=require('node:fs');
const {Sidecar}=require('./sidecar.cjs');
const {CSP,resourcePath,trusted,webPreferences,harden,closeBehavior}=require('./security.cjs');
const {validate}=require('../shared/protocol.cjs');

protocol.registerSchemesAsPrivileged([{scheme:'yuki',privileges:{standard:true,secure:true,supportFetchAPI:true}}]);
const smoke=process.argv.includes('--smoke-test');
const prototype=process.argv.includes('--pet-prototype');
app.setName('yuki');
if(process.env.YUKI_USER_DATA)app.setPath('userData',path.resolve(process.env.YUKI_USER_DATA));
const ownsLock=app.requestSingleInstanceLock();
let window=null,tray=null,sidecar=null,quitting=false,exitWork=null;
let runtimeRoot,uiRoot;
const log=(message)=>{
  try {const folder=app.getPath('logs');fs.mkdirSync(folder,{recursive:true});
    fs.appendFileSync(path.join(folder,'yuki.log'),`${new Date().toISOString()} ${String(message).slice(0,8192)}\n`);}catch{}
};
function showConsole(){if(window&&!window.isDestroyed()){if(window.isMinimized())window.restore();window.show();window.focus();}}
function send(channel,value){if(window&&!window.isDestroyed())window.webContents.send(channel,value);}
function guard(event){if(!trusted(event,window))throw new Error('拒绝未知页面的桌面请求');}
async function stopAndQuit(){
  if(exitWork)return exitWork;
  quitting=true;
  exitWork=(async()=>{await sidecar?.stop();tray?.destroy();tray=null;app.quit();})();
  return exitWork;
}
function configureIpc(){
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
    const perform=(name,payload={})=>sidecar.request(name,payload).catch(error=>{log(error);send('yuki:disconnected',error.message);});
    tray.setContextMenu(Menu.buildFromTemplate([
      {label:'打开 yuki 工作台',click:showConsole},
      {label:'显示 / 隐藏 yuki',click:()=>void perform('toggle_visibility')},
      {label:'暂停 / 继续走动',click:()=>void perform('toggle_pause')},
      {type:'separator'},{label:'保存并退出 yuki',click:()=>void stopAndQuit()},
    ]));
    tray.on('click',showConsole);tray.on('double-click',showConsole);
  }catch(error){log(`托盘不可用：${error.message}`);tray=null;}
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
  protocol.handle('yuki',async request=>{
    try {
      const url=new URL(request.url);
      const target=url.pathname.startsWith('/pet-assets/')
        ?resourcePath('yuki://app/'+url.pathname.slice('/pet-assets/'.length),path.join(runtimeRoot,'assets'))
        :resourcePath(request.url,uiRoot);
      const ext=path.extname(target).toLowerCase();
      const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css',
        '.json':'application/json','.png':'image/png','.ico':'image/x-icon','.svg':'image/svg+xml','.woff2':'font/woff2'}[ext];
      if(!mime)return new Response('Forbidden',{status:403});
      return new Response(await fs.promises.readFile(target),{headers:{'content-type':mime,'Content-Security-Policy':CSP,'X-Content-Type-Options':'nosniff'}});
    }catch{return new Response('Not found',{status:404});}
  });
  session.defaultSession.setPermissionRequestHandler((_web,_permission,callback)=>callback(false));
  session.defaultSession.setPermissionCheckHandler(()=>false);
  session.defaultSession.webRequest.onBeforeRequest((details,callback)=>callback({cancel:!details.url.startsWith('yuki://app/')&&!details.url.startsWith('data:')}));
}
async function createConsole(){
  window=new BrowserWindow({title:'yuki · 桌面小屋',width:1180,height:820,minWidth:880,minHeight:640,
    show:!smoke,backgroundColor:'#FAF9F6',webPreferences:webPreferences(path.join(__dirname,'../preload/console.cjs'))});
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
    sidecar.on('message',message=>{send('yuki:message',message);
      if(message.name==='open_console')showConsole();if(message.name==='exit_app')void stopAndQuit();});
    sidecar.on('disconnected',reason=>{send('yuki:disconnected',reason);if(!quitting)showConsole();});
    sidecar.on('log',log);
    configureIpc();
    createTray();
    await createConsole();
    await sidecar.start();
    if(smoke)await require('./smoke.cjs').run({app,window,sidecar,tray,stopAndQuit,log});
  }).catch(async error=>{log(error.stack||error.message);
    if(smoke){console.error(error);process.exitCode=1;await sidecar?.stop();app.exit(1);}
    else {dialog.showErrorBox('yuki 启动失败',error.message);await stopAndQuit();}
  });
}
