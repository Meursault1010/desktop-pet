'use strict';
const {spawn}=require('node:child_process');
const {EventEmitter}=require('node:events');
const path=require('node:path');
const fs=require('node:fs');
function executable(){
 const root=path.resolve(__dirname,'../../../..');
 const packaged=path.join(process.resourcesPath||'','selection/yuki-selection.exe');
 const file=fs.existsSync(packaged)?packaged:path.join(root,'.electron-build/selection/yuki-selection.exe');
 if(!fs.existsSync(file))throw Error('取词组件未安装，请运行 build-selection.ps1 并重新打包');
 return file;
}
function query(exe,args,timeout=1200){
 return new Promise((resolve,reject)=>{
  const child=spawn(exe,args,{windowsHide:true,stdio:['ignore','pipe','ignore']});let output='',settled=false;
  const finish=(error,value)=>{if(settled)return;settled=true;clearTimeout(timer);error?reject(error):resolve(value);};
  const timer=setTimeout(()=>{child.kill();finish(Error('timeout'));},timeout);
  child.on('error',()=>finish(Error('unavailable')));
  child.stdout.setEncoding('utf8');child.stdout.on('data',chunk=>{output+=chunk;if(output.length>50000){child.kill();finish(Error('overflow'));}});
  child.on('close',()=>{try{finish(null,JSON.parse(output.trim()));}catch{finish(Error('unavailable'));}});
 });
}
class SelectionWatcher extends EventEmitter {
 constructor({exclude=()=>[],suppressClipboard=()=>{},launch=spawn,read=query,getExecutable=executable}={}){super();Object.assign(this,{exclude,suppressClipboard,launch,read,getExecutable});this.generation=0;this.cooldown=new Map();}
 start(){
  if(this.child)return;const exe=this.getExecutable(),generation=++this.generation;
  this.child=this.launch(exe,['watch',[process.pid,...this.exclude()].join(',')],{windowsHide:true,stdio:['ignore','pipe','ignore']});
  let pending='';this.child.stdout.setEncoding('utf8');this.child.stdout.on('data',chunk=>{
   pending+=chunk;if(pending.length>65536){pending='';return;}
   const lines=pending.split('\n');pending=lines.pop();for(const line of lines){try{const event=JSON.parse(line);if(event.kind==='selection'&&/^\d{1,20}$/.test(event.hwnd)&&Number.isFinite(event.x)&&Number.isFinite(event.y))void this.capture(exe,event,generation);}catch{}}
  });
  this.child.once('error',()=>{this.child=null;this.emit('unavailable');});
  this.child.once('exit',()=>{if(generation===this.generation){this.child=null;this.emit('unavailable');}});
 }
 async capture(exe,event,generation){
  const ticket=this.ticket=(this.ticket||0)+1;
  if(this.busy){this.queued={exe,event,generation};return;}this.busy=true;
  try{
   let result={};
   if(Date.now()>(this.cooldown.get(event.hwnd)||0)){
    try{result=await this.read(exe,['uia',event.hwnd,String(event.x),String(event.y)]);}catch{this.cooldown.set(event.hwnd,Date.now()+10000);}
   }
   if(generation!==this.generation||ticket!==this.ticket||result.blocked)return;
   if(!result.text){
    this.suppressClipboard(3000);
    try{result=await this.read(exe,['copy',event.hwnd],1800);}catch{return;}
    finally{this.suppressClipboard(800);}
   }
   if(generation===this.generation&&ticket===this.ticket&&typeof result.text==='string'&&result.text.trim())this.emit('text',{...event,text:result.text.trim()});
  }finally{this.busy=false;const next=this.queued;this.queued=null;if(next&&next.generation===this.generation)void this.capture(next.exe,next.event,next.generation);}
 }
 stop(){this.generation++;this.queued=null;this.child?.kill();this.child=null;this.cooldown.clear();}
}
module.exports={SelectionWatcher,query,executable};
