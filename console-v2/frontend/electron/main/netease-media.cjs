'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {spawn}=require('node:child_process');
function executable(){
 const packaged=path.join(process.resourcesPath||'','media/yuki-media.exe');
 return fs.existsSync(packaged)?packaged:path.resolve(__dirname,'../../../../.electron-build/media/yuki-media.exe');
}
function neteaseMedia(value={command:'snapshot'},{signal,spawnImpl=spawn,timeout=3500}={}){
 const {command}=value;
 if(!['snapshot','play','pause','previous','next','seek'].includes(command))return Promise.reject(Error('媒体控制参数无效'));
 if(command!=='snapshot'&&!/^netease-uia:\d+:\d+$/.test(value.app||''))return Promise.reject(Error('网易云播放器已切换'));
 if(command==='seek'&&(!Number.isFinite(value.position)||value.position<0||typeof value.title!=='string'||typeof value.artist!=='string'))return Promise.reject(Error('播放进度无效'));
 return new Promise((resolve,reject)=>{
  let child,timer,done=false,output='';
  const finish=(err,result)=>{if(done)return;done=true;clearTimeout(timer);signal?.removeEventListener('abort',abort);if(err){child?.kill();reject(err);}else resolve(result);};
  const abort=()=>finish(Error('网易云读取已取消'));
  if(signal?.aborted){abort();return;}
  try{
   child=spawnImpl(executable(),[command,...(command==='snapshot'?[]:[value.app]),...(command==='seek'?[String(value.position),value.title,value.artist]:[])],{windowsHide:true,stdio:['ignore','pipe','ignore']});
   timer=setTimeout(()=>finish(Error('网易云响应超时')),timeout);signal?.addEventListener('abort',abort,{once:true});
   child.stdout.setEncoding('utf8');child.stdout.on('data',chunk=>{output+=chunk;if(output.length>32768)finish(Error('网易云返回数据异常'));});
   child.on('error',()=>finish(Error('网易云兼容组件不可用')));
   child.on('close',code=>{if(done)return;try{const result=JSON.parse(output.trim());if(code!==0||!result.ok||typeof result.media?.available!=='boolean')throw Error(result.error||'网易云返回数据异常');finish(null,result.media);}catch(e){finish(e);}});
  }catch(e){finish(e);}
 });
}
// Music workbench prefers a detected NetEase track to unrelated video sessions.
// An explicitly paused NetEase yields to an actively playing system session.
function selectMedia(system,native){return native?.available&&(native.status!=='Paused'||system?.status!=='Playing')?native:system||{available:false};}
module.exports={neteaseMedia,selectMedia};
