'use strict';
// Both presentations are ordinary movable/resizable windows, with separate bounds.
function fitBounds(bounds,area){
 const width=Math.min(area.width,Math.max(520,bounds.width));
 const height=Math.min(area.height,Math.max(420,bounds.height));
 return {width:Math.round(width),height:Math.round(height),x:Math.round(Math.max(area.x,Math.min(bounds.x,area.x+area.width-width))),y:Math.round(Math.max(area.y,Math.min(bounds.y,area.y+area.height-height)))};
}
const transitions=new WeakMap();
function animateBounds(window,from,to){
 const start=performance.now();
 let timer;
 const stop=()=>{
  clearTimeout(timer);
  window.removeListener('will-resize',stop);
  window.removeListener('will-move',stop);
  window.removeListener('closed',stop);
  transitions.delete(window);
 };
 const step=()=>{
  if(window.isDestroyed()){stop();return;}
  const progress=Math.min(1,(performance.now()-start)/380);
  const eased=1-Math.pow(1-progress,2.7);
  const bounds=Object.fromEntries(Object.keys(to).map(key=>[
   key,Math.round(from[key]+(to[key]-from[key])*eased),
  ]));
  window.setBounds(bounds);
  if(progress<1)timer=setTimeout(step,17);
  else stop();
 };
 transitions.set(window,stop);
 window.on('will-resize',stop);
 window.on('will-move',stop);
 window.once('closed',stop);
 timer=setTimeout(step,17);
}
function setWindowMode(window,screen,wide,animate=false){
 const current=window.getBounds(),area=screen.getDisplayMatching(current).workArea;
 const previous=window._workbenchWide??false;
 if(previous===wide)return {wide};
 const stop=transitions.get(window);
 const maximized=window.isMaximized();
 if(!maximized&&!stop)window[previous?'_expandedBounds':'_compactBounds']=current;
 stop?.();
 if(maximized)window.unmaximize();
 const defaults=wide?{x:area.x+24,y:area.y+24,width:area.width-48,height:area.height-48}:{x:current.x,y:current.y,width:900,height:740};
 const target=fitBounds(window[wide?'_expandedBounds':'_compactBounds']||defaults,area);
 if(animate&&!maximized&&window.isVisible())animateBounds(window,current,target);
 else window.setBounds(target);
 window._workbenchWide=wide;
 return {wide};
}
module.exports={fitBounds,setWindowMode};
