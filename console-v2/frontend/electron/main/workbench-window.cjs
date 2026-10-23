'use strict';
// Both presentations are ordinary movable/resizable windows, with separate bounds.
function fitBounds(bounds,area){
 const width=Math.min(area.width,Math.max(520,bounds.width));
 const height=Math.min(area.height,Math.max(420,bounds.height));
 return {width:Math.round(width),height:Math.round(height),x:Math.round(Math.max(area.x,Math.min(bounds.x,area.x+area.width-width))),y:Math.round(Math.max(area.y,Math.min(bounds.y,area.y+area.height-height)))};
}
function setWindowMode(window,screen,wide){
 const current=window.getBounds(),area=screen.getDisplayMatching(current).workArea;
 const previous=window._workbenchWide??false;
 if(previous===wide)return {wide};
 if(!window.isMaximized())window[previous?'_expandedBounds':'_compactBounds']=current;
 if(window.isMaximized())window.unmaximize();
 const defaults=wide?{x:area.x+24,y:area.y+24,width:area.width-48,height:area.height-48}:{x:current.x,y:current.y,width:900,height:740};
 window.setBounds(fitBounds(window[wide?'_expandedBounds':'_compactBounds']||defaults,area));
 window._workbenchWide=wide;
 return {wide};
}
module.exports={fitBounds,setWindowMode};
