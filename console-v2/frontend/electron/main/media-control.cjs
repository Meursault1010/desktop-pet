'use strict';
const path=require('node:path');
const {spawn}=require('node:child_process');
const commands=new Set(['play','pause','previous','next','seek']);

function controlMedia(value,{spawnImpl=spawn,platform=process.platform,signal,timeout=10000}={}){
  if(!value||!commands.has(value.command)||typeof value.app!=='string'||!value.app||value.app.length>512)return Promise.reject(new Error('媒体控制参数无效'));
  if(value.command==='seek'&&(!Number.isFinite(value.position)||value.position<0||value.position>31536000))return Promise.reject(new Error('播放进度无效'));
  if(value.command==='seek'&&(typeof value.title!=='string'||typeof value.artist!=='string'))return Promise.reject(new Error('当前曲目信息无效'));
  if(platform!=='win32')return Promise.reject(new Error('媒体控制仅支持 Windows'));
  return new Promise((resolve,reject)=>{
    let child,timer,output='',done=false;
    const finish=(error,result)=>{
      if(done)return;done=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);
      if(error){child?.kill();reject(error);}else resolve(result);
    };
    const abort=()=>finish(new Error('媒体控制已取消'));
    if(signal?.aborted){abort();return;}
    try{
      child=spawnImpl('powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',path.join(__dirname,'windows-media.ps1'),'-Command',value.command,'-ExpectedApp',value.app,...(value.command==='seek'?['-ExpectedTitle',value.title,'-ExpectedArtist',value.artist,'-Position',String(value.position)]:[])],{windowsHide:true,stdio:['ignore','pipe','pipe']});
      timer=setTimeout(()=>finish(new Error('播放器响应超时，请检查系统播放器')),timeout);
      signal?.addEventListener('abort',abort,{once:true});
      child.stdout.setEncoding('utf8');child.stdout.on('data',chunk=>{output+=chunk;if(output.length>32768)finish(new Error('播放器返回数据异常'));});
      child.stderr.resume();
      child.on('error',()=>finish(new Error('Windows 媒体控制服务无法启动')));
      child.on('close',code=>{
        if(done)return;
        try{
          const result=JSON.parse(output.replace(/^\uFEFF/,'').trim());
          if(code!==0||!result.ok)throw new Error(result.error||'播放器未接受操作');
          if(!result.media||typeof result.media.available!=='boolean')throw new Error('播放器返回数据异常');
          finish(null,result.media);
        }catch(error){finish(new Error(error instanceof SyntaxError?'播放器返回数据异常':error.message));}
      });
    }catch{finish(new Error('Windows 媒体控制服务无法启动'));}
  });
}
module.exports={controlMedia};
