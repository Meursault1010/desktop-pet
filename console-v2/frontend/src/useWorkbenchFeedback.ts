import {useEffect,type RefObject} from 'react';

export const workbenchSpring='linear(0,.10 8%,.43 20%,.76 34%,.95 52%,1.016 74%,1)';

const groups='[data-sort-scope="main-navigation"], .subtabs > .sortable-navigation, .segmented';
const selected='[aria-current="page"], [aria-selected="true"], [aria-pressed="true"], button.selected';

export function useWorkbenchFeedback(main:RefObject<HTMLElement|null>,reduced:boolean){
 useEffect(()=>{
  const panel=main.current;
  const shell=panel?.closest<HTMLElement>('.observatory');
  if(!panel||!shell)return;
  const system=window.matchMedia('(prefers-reduced-motion: reduce)');
  const tracked=new Map<HTMLElement,HTMLElement>();
  let resize:Animation|undefined;
  let frame=0;

  const clearGroup=(group:HTMLElement)=>{
   delete group.dataset.selectionTrack;
   for(const name of ['x','y','width','height'])group.style.removeProperty('--selection-'+name);
  };
  const sync=()=>{
   const present=new Set(shell.querySelectorAll<HTMLElement>(groups));
   for(const [group,button] of tracked){
    if(present.has(group))continue;
    observer.unobserve(group);
    observer.unobserve(button);
    tracked.delete(group);
    clearGroup(group);
   }
   for(const group of present){
    const button=group.querySelector<HTMLElement>(selected);
    const previous=tracked.get(group);
    if(!button||button.getClientRects().length===0){
     clearGroup(group);
     continue;
    }
    if(previous!==button){
     if(previous)observer.unobserve(previous);
     else observer.observe(group);
     observer.observe(button);
     tracked.set(group,button);
    }
    group.dataset.selectionTrack=group.matches('.segmented')?'pill':group.closest('.subtabs')?'tab':'nav';
    let x=0,y=0,node:HTMLElement|null=button;
    while(node&&node!==group){
     x+=node.offsetLeft;
     y+=node.offsetTop;
     node=node.offsetParent instanceof HTMLElement?node.offsetParent:null;
     if(node&&node!==group){x+=node.clientLeft;y+=node.clientTop;}
    }
    const dimensions={x,y,width:button.offsetWidth,height:button.offsetHeight};
    for(const [name,value] of Object.entries(dimensions)){
     const key='--selection-'+name,length=Math.round(value*10)/10+'px';
     if(group.style.getPropertyValue(key)!==length)group.style.setProperty(key,length);
    }
   }
  };
  const observer=new ResizeObserver(sync);
  const changes=new MutationObserver(records=>{
   if(records.some(record=>record.target instanceof Element&&(
    record.target.closest(groups)||record.type==='childList'&&[...record.addedNodes,...record.removedNodes].some(node=>
     node instanceof Element&&(node.matches(groups)||node.querySelector(groups)),
    )
   )))sync();
  });
  const stopResize=()=>resize?.cancel();
  const onResize=()=>{
   if(reduced||system.matches||document.hidden||frame)return;
   frame=window.requestAnimationFrame(()=>{
    frame=0;
    if(resize){resize.currentTime=0;resize.play();return;}
    const line='2px solid color-mix(in srgb, var(--accent) 46%, transparent)';
    resize=panel.animate([
     {outline:line,outlineOffset:'-2px'},
     {outline:'2px solid transparent',outlineOffset:'-2px'},
    ],{duration:290,easing:'ease-out'});
   });
  };
  sync();
  changes.observe(shell,{subtree:true,childList:true,attributes:true,attributeFilter:['aria-current','aria-selected','aria-pressed']});
  window.addEventListener('resize',onResize);
  system.addEventListener('change',stopResize);
  return()=>{
   window.cancelAnimationFrame(frame);
   stopResize();
   for(const group of tracked.keys())clearGroup(group);
   observer.disconnect();
   changes.disconnect();
   window.removeEventListener('resize',onResize);
   system.removeEventListener('change',stopResize);
  };
 },[main,reduced]);
}
