import {useEffect,type RefObject} from 'react';
import {workbenchSpring} from './useWorkbenchFeedback';

export function useScrollEdgeFeedback(
 main:RefObject<HTMLElement|null>,reduced:boolean,slow:boolean,page:string,
){
 useEffect(()=>{
  const root=main.current;
  const system=window.matchMedia('(prefers-reduced-motion: reduce)');
  if(!root||reduced)return;

  const property='--workbench-pull';
  let surface:HTMLElement|undefined;
  let pull=0,timer=0;
  let animation:Animation|undefined;
  const reset=()=>{
   window.clearTimeout(timer);
   animation?.cancel();
   animation=undefined;
   surface?.style.removeProperty(property);
   if(surface)delete surface.dataset.scrollPull;
   surface=undefined;
   pull=0;
  };
  const release=()=>{
   if(!surface)return;
   const target=surface;
   animation=target.animate([{[property]:pull+'px'},{[property]:'0px'}],{
    duration:slow?440:360,easing:workbenchSpring,fill:'forwards',
   });
   animation.onfinish=reset;
  };
  const push=(target:HTMLElement,direction:number,amount:number)=>{
   if(target!==surface)reset();
   if(animation){
    pull=parseFloat(getComputedStyle(target).getPropertyValue(property))||0;
    animation.cancel();
    animation=undefined;
   }
   surface=target;
   if(pull*direction>0)pull=0;
   pull-=direction*Math.min(18,amount*.28)*(1-Math.min(.97,Math.abs(pull)/23));
   target.dataset.scrollPull='';
   target.style.setProperty(property,pull+'px');
   window.clearTimeout(timer);
   timer=window.setTimeout(release,70);
  };
  const scrollSurface=(event:Event)=>event.composedPath().find((node):node is HTMLElement=>
   node instanceof HTMLElement&&root.contains(node)&&node.scrollHeight-node.clientHeight>1
    &&(node===root||/^(auto|scroll|overlay)$/.test(getComputedStyle(node).overflowY)),
  );
  const atEdge=(target:HTMLElement,direction:number)=>direction<0
   ?target.scrollTop<=1:target.scrollHeight-target.clientHeight-target.scrollTop<=1;
  const onWheel=(event:WheelEvent)=>{
   if(system.matches||event.ctrlKey||event.shiftKey||Math.abs(event.deltaY)<=Math.abs(event.deltaX))return;
   const target=scrollSurface(event),direction=Math.sign(event.deltaY);
   if(target&&atEdge(target,direction))push(target,direction,Math.abs(event.deltaY)*(event.deltaMode===1?16:1));
   else if(surface)reset();
  };
  const onKey=(event:KeyboardEvent)=>{
   if(system.matches||event.defaultPrevented||event.target instanceof Element&&event.target.closest(
    'input, select, textarea, button, [contenteditable], [role="tab"]',
   ))return;
   const direction=['Home','PageUp','ArrowUp'].includes(event.key)?-1
    :['End','PageDown','ArrowDown',' '].includes(event.key)?1:0;
   if(!direction)return;
   const target=scrollSurface(event);
   if(target&&atEdge(target,direction))push(target,direction,46);
  };

  root.addEventListener('wheel',onWheel,{passive:true});
  root.addEventListener('keydown',onKey);
  system.addEventListener('change',reset);
  return()=>{
   reset();
   root.removeEventListener('wheel',onWheel);
   root.removeEventListener('keydown',onKey);
   system.removeEventListener('change',reset);
  };
 },[main,reduced,slow,page]);
}
