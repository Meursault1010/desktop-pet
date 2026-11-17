'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');

async function main(){
  const frontend=path.resolve(__dirname,'../..'),project=path.resolve(frontend,'../..');
  const version = fs.readFileSync(path.join(project, 'VERSION'), 'utf8').trim();
  if (!/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/.test(version)) {
    throw new Error('VERSION must be a stable version such as 1.1.2.');
  }
  const root=path.dirname(frontend),work=path.join(project,'.electron-build');
  const backend=path.join(work,'python-dist/yuki-backend');
  if(!fs.existsSync(path.join(backend,'yuki-backend.exe')))throw new Error('Build the frozen Python backend first (build-electron.ps1).');
  const ocr=path.join(work,'ocr-dist/yuki-ocr');
  const selection=path.join(work,'selection');
  const localModel=path.join(project,'local-model/qwen');
  const llamaRuntime=path.join(work,'llama-runtime-b12464');
  if(!fs.existsSync(path.join(localModel,'Qwen3.8-4B-Q4_K_M.gguf')))throw Error('Missing bundled Qwen weights: restore local-model/qwen before packaging.');
  if(!fs.existsSync(path.join(llamaRuntime,'llama-server.exe')))throw Error('Build the pinned llama.cpp runtime first (build-llama-runtime.ps1).');
  if(!fs.existsSync(path.join(selection,'yuki-selection.exe')))throw Error('Build Windows selection helper first (build-selection.ps1).');
  if(!fs.existsSync(path.join(ocr,'yuki-ocr.exe')))throw new Error('Build offline OCR first (build-ocr.ps1).');
  const stage=path.join(work,'app-'+Date.now());fs.mkdirSync(stage,{recursive:true});
  fs.writeFileSync(path.join(stage,'package.json'),JSON.stringify({name:'yuki',version,main:'electron/main/index.cjs',description:'yuki Windows desktop pet',author:'Meursault',private:true},null,2));
  fs.copyFileSync(path.join(project,'THIRD-PARTY-NOTICES.md'),path.join(stage,'THIRD-PARTY-NOTICES.txt'));
  fs.cpSync(path.join(project,'licenses'),path.join(stage,'licenses'),{recursive:true});
  for(const name of ['main','preload','shared','icons'])fs.cpSync(path.join(frontend,'electron',name),path.join(stage,'electron',name),{recursive:true});
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
  for(const dep of ['pdf-parse','mammoth','pinyin-pro'])copyDependency(dep);
  const {packager}=await import('@electron/packager');
  const paths=await packager({dir:stage,name:'yuki',platform:'win32',arch:'x64',
    electronVersion:require('electron/package.json').version,
    out:process.env.YUKI_PACKAGE_OUTPUT?path.resolve(process.env.YUKI_PACKAGE_OUTPUT):path.join(project,'releases/electron/yuki-win32-x64-workbench'),
    overwrite:true,asar:false,prune:false,icon:path.join(frontend,'electron/icons/yuki-desktop-large.ico'),
    appVersion:version,buildVersion:version,win32metadata:{CompanyName:'Meursault',FileDescription:'yuki Electron desktop pet',ProductName:'yuki'}});
  for(const output of paths){
    const bundledModel=path.join(output,'resources/local-model/qwen');
    fs.mkdirSync(bundledModel,{recursive:true});
    fs.copyFileSync(path.join(localModel,'Qwen3.8-4B-Q4_K_M.gguf'),path.join(bundledModel,'Qwen3.8-4B-Q4_K_M.gguf'));
    fs.cpSync(llamaRuntime,path.join(bundledModel,'runtime'),{recursive:true});
    fs.copyFileSync(path.join(localModel,'README.md'),path.join(bundledModel,'MODEL-NOTICE.txt'));
    fs.cpSync(selection,path.join(output,'resources/selection'),{recursive:true});
    fs.cpSync(ocr,path.join(output,'resources/ocr'),{recursive:true});
    const pet=path.join(output,'resources/pet');fs.mkdirSync(pet,{recursive:true});
    fs.cpSync(backend,path.join(pet,'python'),{recursive:true});
    // Retain readable Python sources; the frozen backend already contains the only asset copy.
    for(const name of fs.readdirSync(root))if(name.endsWith('.py')&&!name.startsWith('test_'))fs.copyFileSync(path.join(root,name),path.join(pet,name));
    fs.writeFileSync(path.join(output,'使用说明.txt'),[
      'yuki · Windows 桌面伙伴',
      '双击 yuki.exe。完整目录一起移动，不要单独复制 EXE。',
      '内含 Electron、Python/PySide6、离线 OCR 和运行素材，无需全局 Python/Node/Rust。',
      '工作台包含总览、角色、AI 助手、工具、设置；支持雪白、银雾、星夜主题和宽窄窗口切换。',
      '总览采用固定布局，显示雪的状态、今日足迹、陪伴节奏与电脑状态。右键宠物可快捷聊天、使用常用工具、打开工作台和退出。',
      '宠物设置继续保存在 %LOCALAPPDATA%\\XiaoJu\\DesktopPet\\settings.ini；工作台设置保存在 Electron 用户数据目录。',
      '内置本地模型默认关闭，可在设置中启用；也可连接兼容的本地服务或用户选择的云端 API。云端服务会收到用户发送的内容；AI 助手不提供联网检索。',
      '今日摘要依据运行期间的实际事件；音乐互动只检测本机播放声音并驱动舞动，不提供播放器控制；提醒需要保持 Yuki 运行。',
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
