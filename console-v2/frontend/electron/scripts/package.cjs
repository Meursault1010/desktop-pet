'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');

async function main(){
  const frontend=path.resolve(__dirname,'../..'),project=path.resolve(frontend,'../..');
  const root=path.dirname(frontend),work=path.join(project,'.electron-build');
  const backend=path.join(work,'python-dist/yuki-backend');
  if(!fs.existsSync(path.join(backend,'yuki-backend.exe')))throw new Error('Build the frozen Python backend first (build-electron.ps1).');
  const stage=path.join(work,'app-'+Date.now());fs.mkdirSync(stage,{recursive:true});
  fs.writeFileSync(path.join(stage,'package.json'),JSON.stringify({name:'yuki',version:'1.1.0',main:'electron/main/index.cjs',description:'yuki Windows desktop pet',author:'Meursault',private:true},null,2));
  for(const name of ['main','preload','shared'])fs.cpSync(path.join(frontend,'electron',name),path.join(stage,'electron',name),{recursive:true});
  fs.copyFileSync(path.join(frontend,'src-tauri/icons/icon.ico'),path.join(stage,'electron/icon.ico'));
  fs.cpSync(path.join(frontend,'dist'),path.join(stage,'dist'),{recursive:true});
  const {packager}=await import('@electron/packager');
  const paths=await packager({dir:stage,name:'yuki',platform:'win32',arch:'x64',
    electronVersion:require('electron/package.json').version,
    out:process.env.YUKI_PACKAGE_OUTPUT?path.resolve(process.env.YUKI_PACKAGE_OUTPUT):path.join(project,'releases/electron/yuki-win32-x64-breathing'),
    overwrite:true,asar:false,prune:false,icon:path.join(frontend,'src-tauri/icons/icon.ico'),
    appVersion:'1.1.0',buildVersion:'1.1.0',win32metadata:{CompanyName:'Meursault',FileDescription:'yuki Electron desktop pet',ProductName:'yuki'}});
  for(const output of paths){
    const pet=path.join(output,'resources/pet');fs.mkdirSync(pet,{recursive:true});
    fs.cpSync(backend,path.join(pet,'python'),{recursive:true});
    // Retain readable sources and relative runtime assets without personal reference images or configs.
    for(const name of fs.readdirSync(root))if(name.endsWith('.py')&&!name.startsWith('test_'))fs.copyFileSync(path.join(root,name),path.join(pet,name));
    fs.cpSync(path.join(root,'assets'),path.join(pet,'assets'),{recursive:true});
    fs.writeFileSync(path.join(output,'使用说明.txt'),'yuki Electron 兼容迁移版 1.1.0\r\n双击 yuki.exe。完整目录一起移动，不要单独复制 EXE。\r\n内含 Electron、Python/PySide6 和运行素材，无需全局 Python/Node/Rust。\r\n宠物设置继续保存在 %LOCALAPPDATA%\\XiaoJu\\DesktopPet\\settings.ini。\r\n工作台由 Electron 管理，透明宠物窗口保留 PySide6。\r\n未签名、不是安装器；Electron PNG 窗口仍为独立开发原型。\r\n');
    const acl=spawnSync('icacls',[output,'/grant','*S-1-15-2-1:(OI)(CI)(RX)','/T','/C'],{encoding:'utf8',windowsHide:true});
    if(acl.status!==0)throw new Error(`Unable to grant Electron sandbox read access to ${output}: ${acl.stderr||acl.stdout||acl.error}`);
    console.log('Packaged:',output);
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
