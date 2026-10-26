'use strict';
const path=require('node:path');
const {harden,webPreferences}=require('./security.cjs');
const {position}=require('./lyrics.cjs');
class LyricsWindow {
 constructor({BrowserWindow,screen,lyrics,getMedia}){Object.assign(this,{BrowserWindow,screen,lyrics,getMedia});this.ready=false;this.stopped=false;this.timer=setInterval(()=>this.update(),250);lyrics.changed=()=>this.update();this.update();}
 update(){
  if(this.stopped)return;
  const state=this.lyrics.snapshot(),s=state.settings;
  if(!s.enabled||!s.overlay){this.window?.hide();return;}
  if(!this.window){
   const area=this.screen.getPrimaryDisplay().workArea,width=Math.min(720,area.width),height=156;
   const win=this.window=new this.BrowserWindow({x:Math.round(area.x+(area.width-width)/2),y:Math.round(area.y+area.height-height-50),width,height,minWidth:320,minHeight:120,show:false,frame:false,transparent:true,backgroundColor:'#00000000',hasShadow:false,alwaysOnTop:s.alwaysOnTop,skipTaskbar:true,resizable:true,movable:true,maximizable:false,fullscreenable:false,webPreferences:{...webPreferences(path.join(__dirname,'../preload/lyrics.cjs')),backgroundThrottling:false}});
   harden(win);win.setMenuBarVisibility(false);
   win.on('close',event=>{if(!this.stopped){event.preventDefault();this.lyrics.set({overlay:false});}});
   win.on('closed',()=>{this.window=null;this.ready=false;});
   win.webContents.once('did-finish-load',()=>{this.ready=true;this.lastPayload='';this.update();});
   win.loadURL('yuki://app/lyrics.html').catch(()=>{this.ready=false;this.lyrics.error='桌面歌词加载失败，请关闭后重新打开';});
  }
  if(!this.ready)return;
  this.window.setAlwaysOnTop(s.alwaysOnTop,'floating');
  this.window.setOpacity(s.opacity/100);
  if(!this.window.isVisible())this.window.showInactive();
  const media=this.getMedia();let lines=state.lines;
  if(state.timed){const p=position(media)-(media.start||0);let index=-1;for(let i=0;i<lines.length&&lines[i].at<=p;i++)index=i;lines=lines.slice(Math.max(0,index),Math.max(0,index)+2);}
  else lines=lines.slice(0,1);
  const payload={...state,lines,media},serialized=JSON.stringify(payload);
  if(serialized!==this.lastPayload){this.lastPayload=serialized;this.window.webContents.send('yuki:lyrics-state',payload);}
 }
 stop(){this.stopped=true;clearInterval(this.timer);this.lyrics.changed=null;this.window?.destroy();this.window=null;}
}
module.exports={LyricsWindow};
