'use strict';
const path=require('node:path');
const {webPreferences,harden,trusted}=require('./security.cjs');
const {popupBounds}=require('./translation.cjs');
class TranslationWindows {
 constructor({BrowserWindow,screen,desktopCapturer,ipcMain,nativeImage,clipboard,translation,ocr}){
  Object.assign(this,{BrowserWindow,screen,desktopCapturer,ipcMain,nativeImage,clipboard,translation,ocr});
  ipcMain.handle('yuki:translation-view',event=>{this.guard(event,this.popup);return translation.snapshot();});
  ipcMain.handle('yuki:translation-edit',async(event,source)=>{
   this.guard(event,this.popup);
   if(typeof source!=='string'||source.length>4000)throw Error('原文长度无效');
   const value=source.trim();
   if(!value){translation.cancel();translation.update({source:'',text:'',error:'',target:'',phase:'idle'});return translation.snapshot();}
   await translation.edit(value);return translation.snapshot();
  });
  ipcMain.handle('yuki:translation-gesture',(event,input)=>{
   this.guard(event,this.popup);
   if(!input||Object.keys(input).some(key=>!['phase','kind','x','y'].includes(key))||!['start','update','end'].includes(input.phase))throw Error('窗口操作无效');
   if(input.phase!=='end'&&![input.x,input.y].every(value=>Number.isFinite(value)&&Math.abs(value)<=1000000))throw Error('窗口坐标无效');
   if(input.phase==='start'){
    if(!['move','resize'].includes(input.kind))throw Error('窗口操作无效');
    this.gesture={kind:input.kind,point:{x:input.x,y:input.y},bounds:this.popup.getBounds()};return;
   }
   if(input.phase==='end'){this.gesture=null;return;}
   if(!this.gesture)return;
   const {kind,point,bounds}=this.gesture,cursor={x:input.x,y:input.y},dx=cursor.x-point.x,dy=cursor.y-point.y;
   const area=screen.getDisplayNearestPoint(kind==='move'?cursor:{x:bounds.x,y:bounds.y}).workArea;
   if(kind==='move'){
    const x=Math.round(Math.max(area.x-bounds.width+64,Math.min(bounds.x+dx,area.x+area.width-64))),y=Math.round(Math.max(area.y,Math.min(bounds.y+dy,area.y+area.height-40)));
    // Keep the dimensions captured at pointerdown. Frameless Windows windows
    // can report a transient size while moving (especially across DPI areas);
    // setBounds makes a move incapable of changing the popup's size.
    if(typeof this.popup.setBounds==='function')this.popup.setBounds({x,y,width:bounds.width,height:bounds.height});
    else this.popup.setPosition(x,y);
    this.popupSize={width:bounds.width,height:bounds.height};
   }
   else{const width=Math.round(Math.max(320,Math.min(bounds.width+dx,area.x+area.width-bounds.x))),height=Math.round(Math.max(240,Math.min(bounds.height+dy,area.y+area.height-bounds.y)));this.popup.setSize(width,height);this.popupSize={width,height};}
  });
  ipcMain.handle('yuki:translation-control',async(event,name)=>{
   this.guard(event,this.popup);
   if(name==='close'){this.dismiss();return;}
   if(name==='copy'){const state=translation.snapshot();if(state.phase!=='done'||!state.text)throw Error('翻译尚未完成');await clipboard.writeText(state.text);return;}
   if(name==='retry'){void translation.retry();return;}
   throw Error('未知翻译操作');
  });
  ipcMain.handle('yuki:capture-image',event=>{this.guard(event,this.overlay);return {image:this.captureImage.toDataURL(),width:this.captureSize.width,height:this.captureSize.height};});
  ipcMain.handle('yuki:capture-region',async(event,region)=>{
   this.guard(event,this.overlay);
   if(region===null){this.closeOverlay();return;}
   if(!region||Object.keys(region).sort().join(',')!=='height,width,x,y'||!Object.values(region).every(Number.isFinite))throw Error('框选区域无效');
   const {x,y,width,height}=region;
   if(x<0||y<0||width<5||height<5||x+width>this.captureSize.width+1||y+height>this.captureSize.height+1)throw Error('请框选屏幕内的文字区域');
   const size=this.captureImage.getSize();const sx=size.width/this.captureSize.width,sy=size.height/this.captureSize.height;
   const image=this.captureImage.crop({x:Math.floor(x*sx),y:Math.floor(y*sy),width:Math.max(1,Math.min(size.width-Math.floor(x*sx),Math.round(width*sx))),height:Math.max(1,Math.min(size.height-Math.floor(y*sy),Math.round(height*sy)))});
   const point={x:this.captureDisplay.bounds.x+x+width,y:this.captureDisplay.bounds.y+y+height};
   this.closeOverlay();const generation=++this.captureGeneration,translationGeneration=translation.generation;
   translation.update({source:'',text:'',error:'',method:'ocr',phase:'ocr',target:''});this.show(point);
   try{const result=await ocr.recognize(image.toPNG());if(generation===this.captureGeneration&&translationGeneration===translation.generation&&translation.enabled)await translation.translate(result.text,point,'ocr');}
   catch(error){if(generation===this.captureGeneration&&translationGeneration===translation.generation&&translation.enabled)translation.update({phase:'error',error:String(error.message||error).slice(0,300)});}
  });
  this.captureGeneration=0;
  this.popupSize={width:420,height:360};
  this.onPointerDown=point=>this.dismissOutside(point);
  this.translation.watcher?.on('pointer-down',this.onPointerDown);
 }
 guard(event,window){if(!trusted(event,window))throw Error('拒绝未知页面的翻译请求');}
 async createPopup(){
  if(this.popup&&!this.popup.isDestroyed()){await this.popupReady;return;}
  this.popup=new this.BrowserWindow({...this.popupSize,minWidth:320,minHeight:240,show:false,frame:false,resizable:true,movable:true,maximizable:false,fullscreenable:false,alwaysOnTop:true,skipTaskbar:true,backgroundColor:'#f7fbff',webPreferences:webPreferences(path.join(__dirname,'../preload/translation.cjs'))});
  this.popup.on('resize',()=>{if(this.popup&&!this.popup.isDestroyed()){const [width,height]=this.popup.getSize();this.popupSize={width,height};}});
  harden(this.popup);this.popup.setMenuBarVisibility(false);this.popup.on('closed',()=>{this.popup=null;});
  this.popupReady=this.popup.loadURL('yuki://app/translation.html');await this.popupReady;
 }
 async show(point){
  const generation=this.translation.generation;
  await this.createPopup();if(!this.translation.enabled||generation!==this.translation.generation)return;
  const logical=this.screen.screenToDipPoint({x:Math.round(point.x),y:Math.round(point.y)});
  // OCR points already use Electron's device independent coordinates.
  const at=this.translation.state.method==='ocr'?point:logical;
  const area=this.screen.getDisplayNearestPoint(at).workArea;
  this.popup.setBounds(popupBounds(at,area,this.popupSize));this.popup.showInactive();this.update(this.translation.snapshot());
 }
 update(state){if(this.popup&&!this.popup.isDestroyed())this.popup.webContents.send('yuki:translation-result',state);}
 dismissOutside(point){
  const popup=this.popup;
  if(!popup||popup.isDestroyed()||!popup.isVisible()||this.gesture||this.translation.snapshot().phase!=='done')return;
  const {x,y}=this.screen.screenToDipPoint(point);
  const bounds=popup.getBounds();
  if(x<bounds.x||y<bounds.y||x>=bounds.x+bounds.width||y>=bounds.y+bounds.height)this.dismiss();
 }
 dismiss(){this.captureGeneration++;this.gesture=null;this.translation.cancel();this.popup?.hide();}
 closeOverlay(){this.overlay?.destroy();this.overlay=null;this.captureImage=null;}
 async capture(){
  if(!this.translation.enabled)throw Error('请先开启划线翻译模式');
  if(this.overlay||this.capturing)return;
  this.capturing=true;
  try{
   this.dismiss();this.closeOverlay();
   const generation=this.captureGeneration;
   await new Promise(resolve=>setTimeout(resolve,100));
   const display=this.screen.getDisplayNearestPoint(this.screen.getCursorScreenPoint());
   const sources=await this.desktopCapturer.getSources({types:['screen'],thumbnailSize:{width:Math.ceil(display.size.width*display.scaleFactor),height:Math.ceil(display.size.height*display.scaleFactor)}});
   const source=sources.find(item=>item.display_id===String(display.id));
   if(generation!==this.captureGeneration||!this.translation.enabled)return;
   if(!source||source.thumbnail.isEmpty())throw Error('无法截取当前屏幕，请检查屏幕捕获权限');
   this.captureImage=source.thumbnail;this.captureDisplay=display;this.captureSize=display.size;
   this.overlay=new this.BrowserWindow({...display.bounds,show:false,frame:false,resizable:false,alwaysOnTop:true,skipTaskbar:true,backgroundColor:'#102334',webPreferences:webPreferences(path.join(__dirname,'../preload/capture.cjs'))});
   harden(this.overlay);this.overlay.setMenuBarVisibility(false);this.overlay.on('closed',()=>{this.overlay=null;});
   const overlay=this.overlay;await overlay.loadURL('yuki://app/capture.html');if(!overlay.isDestroyed()&&generation===this.captureGeneration&&this.translation.enabled){overlay.show();overlay.focus();}
  }finally{this.capturing=false;}
 }
 stop(){this.translation.watcher?.off('pointer-down',this.onPointerDown);this.captureGeneration++;this.closeOverlay();this.popup?.destroy();this.popup=null;}
}
module.exports={TranslationWindows};
