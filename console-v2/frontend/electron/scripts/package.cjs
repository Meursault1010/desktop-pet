'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');

async function main(){
  const frontend=path.resolve(__dirname,'../..'),project=path.resolve(frontend,'../..');
  const root=path.dirname(frontend),work=path.join(project,'.electron-build');
  const backend=path.join(work,'python-dist/yuki-backend');
  if(!fs.existsSync(path.join(backend,'yuki-backend.exe')))throw new Error('Build the frozen Python backend first (build-electron.ps1).');
  const ocr=path.join(work,'ocr-dist/yuki-ocr');
  const selection=path.join(work,'selection');
  const localModel=path.join(project,'local-model/qwen');
  if(!fs.existsSync(path.join(localModel,'Qwen3.8-4B-Q4_K_M.gguf'))||!fs.existsSync(path.join(localModel,'runtime/llama-server.exe')))throw Error('Missing bundled Qwen: restore local-model/qwen before packaging.');
  if(!fs.existsSync(path.join(selection,'yuki-selection.exe')))throw Error('Build Windows selection helper first (build-selection.ps1).');
  if(!fs.existsSync(path.join(ocr,'yuki-ocr.exe')))throw new Error('Build offline OCR first (build-ocr.ps1).');
  const stage=path.join(work,'app-'+Date.now());fs.mkdirSync(stage,{recursive:true});
  fs.writeFileSync(path.join(stage,'package.json'),JSON.stringify({name:'yuki',version:'1.1.0',main:'electron/main/index.cjs',description:'yuki Windows desktop pet',author:'Meursault',private:true},null,2));
  for(const name of ['main','preload','shared'])fs.cpSync(path.join(frontend,'electron',name),path.join(stage,'electron',name),{recursive:true});
  fs.copyFileSync(path.join(frontend,'src-tauri/icons/icon.ico'),path.join(stage,'electron/icon.ico'));
  fs.cpSync(path.join(frontend,'dist'),path.join(stage,'dist'),{recursive:true});
  // Only ship the document readers and their installed runtime dependencies.
  const copied=new Set();
  function copyDependency(name,from=frontend,optional=false){
    let cursor=from,source;
    while(cursor.startsWith(frontend)){
      const candidate=path.join(cursor,'node_modules',name);
      if(fs.existsSync(path.join(candidate,'package.json'))){source=candidate;break;}
      const parent=path.dirname(cursor);if(parent===cursor)break;cursor=parent;
    }
    if(!source){if(optional)return;throw Error('Missing runtime dependency: '+name);}
    if(copied.has(source))return;copied.add(source);
    fs.cpSync(source,path.join(stage,path.relative(frontend,source)),{recursive:true});
    const meta=JSON.parse(fs.readFileSync(path.join(source,'package.json'),'utf8'));
    for(const dep of Object.keys(meta.dependencies||{}))copyDependency(dep,source,dep in (meta.optionalDependencies||{}));
    for(const dep of Object.keys(meta.optionalDependencies||{}))copyDependency(dep,source,true);
  }
  for(const dep of ['pdf-parse','mammoth'])copyDependency(dep);
  const {packager}=await import('@electron/packager');
  const paths=await packager({dir:stage,name:'yuki',platform:'win32',arch:'x64',
    electronVersion:require('electron/package.json').version,
    out:process.env.YUKI_PACKAGE_OUTPUT?path.resolve(process.env.YUKI_PACKAGE_OUTPUT):path.join(project,'releases/electron/yuki-win32-x64-workbench'),
    overwrite:true,asar:false,prune:false,icon:path.join(frontend,'src-tauri/icons/icon.ico'),
    appVersion:'1.1.0',buildVersion:'1.1.0',win32metadata:{CompanyName:'Meursault',FileDescription:'yuki Electron desktop pet',ProductName:'yuki'}});
  for(const output of paths){
    const bundledModel=path.join(output,'resources/local-model/qwen');
    fs.mkdirSync(bundledModel,{recursive:true});
    fs.copyFileSync(path.join(localModel,'Qwen3.8-4B-Q4_K_M.gguf'),path.join(bundledModel,'Qwen3.8-4B-Q4_K_M.gguf'));
    fs.cpSync(path.join(localModel,'runtime'),path.join(bundledModel,'runtime'),{recursive:true});
    fs.cpSync(selection,path.join(output,'resources/selection'),{recursive:true});
    fs.cpSync(ocr,path.join(output,'resources/ocr'),{recursive:true});
    const pet=path.join(output,'resources/pet');fs.mkdirSync(pet,{recursive:true});
    fs.cpSync(backend,path.join(pet,'python'),{recursive:true});
    // Retain readable Python sources; the frozen backend already contains the only asset copy.
    for(const name of fs.readdirSync(root))if(name.endsWith('.py')&&!name.startsWith('test_'))fs.copyFileSync(path.join(root,name),path.join(pet,name));
    fs.writeFileSync(path.join(output,'使用说明.txt'),[
      'yuki Electron 工作台重做版 · 2026-10-20',
      '双击 yuki.exe。完整目录一起移动，不要单独复制 EXE。',
      '内含 Electron、Python/PySide6、离线 OCR 和运行素材，无需全局 Python/Node/Rust。',
      '工作台包含总览、角色、AI 助手、工具、设置；支持雪白、银雾、星夜主题和宽窄窗口切换。',
      '总览可添加、拖动、调整区块大小并保存自定义页面。右键宠物可快捷聊天、切换划词翻译、打开工作台和退出。',
      '宠物设置继续保存在 %LOCALAPPDATA%\\XiaoJu\\DesktopPet\\settings.ini；工作台设置保存在 Electron 用户数据目录。',
      '内置 Qwen 4B 本地模型，打开 Yuki 自动加载，无需另开 LM Studio；首次加载需稍等。模型连接页也可切换其他本地服务或远程 API。',
      '今日摘要依据运行期间收集的事件；播放器状态为只读；提醒需要保持 Yuki 运行。',
      '工作台由 Electron 管理，透明宠物窗口保留 PySide6；未签名的便携版，不是安装器。',
      '更新前请先通过旧版 Yuki 菜单保存并退出，再运行新版。',
      ''
    ].join('\r\n'));
    const acl=spawnSync('icacls',[output,'/grant','*S-1-15-2-1:(OI)(CI)(RX)','/T','/C','/Q'],{encoding:'utf8',windowsHide:true});
    if(acl.status!==0)throw new Error(`Unable to grant Electron sandbox read access to ${output}: ${acl.stderr||acl.stdout||acl.error}`);
    console.log('Packaged:',output);
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
