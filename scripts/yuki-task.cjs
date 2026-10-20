#!/usr/bin/env node
'use strict';
// Explicit task integration: report the exit status without scraping terminals.
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const {randomUUID}=require('node:crypto');
const {spawn}=require('node:child_process');
function notify(kind,text){
  const root=process.env.YUKI_EVENT_DIR||path.join(process.env.YUKI_USER_DATA||path.join(process.env.APPDATA||path.join(os.homedir(),'AppData','Roaming'),'yuki'),'events');
  fs.mkdirSync(root,{recursive:true});
  const file=path.join(root,randomUUID()+'.json');
  const temp=file+'.tmp';
  fs.writeFileSync(temp,JSON.stringify({kind,text:String(text).slice(0,180)}));
  fs.renameSync(temp,file);
}
function main(args){
  if(args[0]==='--notify'){
    if(!['success','failure','download'].includes(args[1])||!args.slice(2).join(' ').trim())throw Error('用法：--notify success|failure|download "消息"');
    notify(args[1],args.slice(2).join(' '));return;
  }
  if(args[0]!=='--'||args.length<2)throw Error('用法：node scripts/yuki-task.cjs -- npm run build');
  const [command,...commandArgs]=args.slice(1);
  let child;
  // Resolve Node package manager entry points without a shell, preserving
  // Chinese paths, spaces and literal arguments on Windows.
  if(process.platform==='win32'&&/^(npm|npx)(\.cmd)?$/i.test(command)){
    const tool=command.toLowerCase().startsWith('npx')?'npx':'npm';
    const cli=tool==='npm'&&process.env.npm_execpath?process.env.npm_execpath:path.join(path.dirname(process.execPath),'node_modules','npm','bin',tool+'-cli.js');
    if(!fs.existsSync(cli))throw Error('未找到 '+tool+' 的 Node 入口，请使用 node 加脚本路径运行任务。');
    child=spawn(process.execPath,[cli,...commandArgs],{stdio:'inherit',windowsHide:true});
  }else child=spawn(command,commandArgs,{stdio:'inherit',windowsHide:true});
  let reported=false;
  const report=(kind,text)=>{if(reported)return;reported=true;try{notify(kind,text);}catch(error){console.error('Yuki 通知失败：'+error.message);}};
  child.once('error',error=>{report('failure','任务无法启动：'+command);console.error(error.message);process.exitCode=1;});
  child.once('exit',(code,signal)=>{report(code===0?'success':'failure',code===0?'任务完成：'+command:'任务失败：'+command+(signal?' ('+signal+')':''));process.exitCode=code??1;});
}
if(require.main===module){try{main(process.argv.slice(2));}catch(error){console.error(error.message);process.exitCode=1;}}
module.exports={notify,main};
