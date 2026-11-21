import {useSyncExternalStore} from 'react';
import {host} from './host';

type Precision='second'|'minute'|'day'|'off';
type Listener=()=>void;
let visible=!document.hidden;
let subscriptions=0;
let disconnectVisibility:(()=>void)|undefined;

function localMidnight(now:number,offset=0){
 const date=new Date(now);
 return new Date(date.getFullYear(),date.getMonth(),date.getDate()+offset).getTime();
}

function makeClock(bucket:(now:number)=>number,next:(now:number)=>number){
 const listeners=new Set<Listener>();
 let current=bucket(Date.now()),timer:number|undefined;
 const sync=()=>{
  if(timer!==undefined){window.clearTimeout(timer);timer=undefined;}
  if(!visible||!listeners.size)return;
  const now=Date.now(),updated=bucket(now);
  if(current!==updated){
   current=updated;
   for(const listener of listeners)listener();
  }
  timer=window.setTimeout(sync,Math.max(1,next(now)-now));
 };
 return {
  sync,
  snapshot:()=>current,
  subscribe(listener:Listener){
   listeners.add(listener);
   if(++subscriptions===1)disconnectVisibility=watchVisibility();
   if(listeners.size===1)sync();
   return ()=>{
    listeners.delete(listener);
    if(!listeners.size)sync();
    if(--subscriptions===0){disconnectVisibility?.();disconnectVisibility=undefined;}
   };
  },
 };
}

const intervals=(period:number)=>makeClock(
 now=>Math.floor(now/period)*period,
 now=>Math.floor(now/period)*period+period,
);
const clocks={second:makeClock(now=>now,now=>now+1000),minute:intervals(60000),day:makeClock(localMidnight,now=>localMidnight(now,1))};
const idleClock={snapshot:()=>0,subscribe:()=>()=>{}};

function watchVisibility(){
 let active=true,hasNativeUpdate=false;
 const update=(next:boolean)=>{
  if(visible===next)return;
  visible=next;
  for(const clock of Object.values(clocks))clock.sync();
 };
 const browserVisibility=()=>update(!document.hidden);
 let unsubscribe:(()=>void)|undefined;
 if(host?.workbenchVisibilitySubscribe){
  unsubscribe=host.workbenchVisibilitySubscribe(value=>{hasNativeUpdate=true;update(value);});
  void host.workbenchVisibility?.().then(value=>{if(active&&!hasNativeUpdate)update(value);}).catch(()=>{});
 }else{
  browserVisibility();
  document.addEventListener('visibilitychange',browserVisibility);
 }
 return()=>{active=false;unsubscribe?.();document.removeEventListener('visibilitychange',browserVisibility);};
}

/** Suspend display-only clocks while hidden and resync with wall time on restore. */
export function useNow(precision:Precision='second'){
 const clock=precision==='off'?idleClock:clocks[precision];
 return useSyncExternalStore(clock.subscribe,clock.snapshot,clock.snapshot);
}
