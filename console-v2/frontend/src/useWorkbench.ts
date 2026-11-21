import {useCallback,useEffect,useRef,useState} from 'react';
import {host} from './host';
import type {DesktopSnapshot,TimersSnapshot,TimersTodoChange} from './host/types';
import {readStore,saveStore,validTodos,validFocus,validHealth,type Focus,type Todo} from './workspaceModel';
type Health=ReturnType<typeof validHealth>;
const empty:DesktopSnapshot={clipboard:[],clipboardPaused:false,media:{available:false},battery:{available:false},events:[],weather:null,city:'',inbox:''};
const MIGRATED='yuki-v2-timers-in-main';
export function useWorkbench(active=true){
 const [data,setData]=useState(empty),[error,setError]=useState(''),[busy,setBusy]=useState('');
 // The main process owns focus, todos and health reminders: it stores absolute deadlines and
 // fires them even while this window is closed. The page only edits the list and displays it,
 // mirroring each snapshot back into local storage purely so the first paint is not blank.
 const cached=useRef<TimersSnapshot|null>(null);
 if(!cached.current)cached.current={serverTime:0,focus:validFocus(readStore('focus',null)),todos:validTodos(readStore('todos',[])),health:validHealth(readStore('health',null))};
 const [timers,setTimersState]=useState<TimersSnapshot|null>(null);
 const revision=useRef(-1);
 const lastTimers=useRef<TimersSnapshot|null>(null);
 function setTimers(value:TimersSnapshot|null){
  if(!value||(value.revision!==undefined&&value.revision<=revision.current))return;
  if(value.revision!==undefined)revision.current=value.revision;
  lastTimers.current=value;
  setTimersState(value);
  try{saveStore('focus',value.focus);saveStore('todos',value.todos);saveStore('health',value.health);}catch{/* the cache is a convenience, not a source of truth */}
 }
 const {focus,todos,health}=timers??cached.current;
 const focusRef=useRef(focus);
 focusRef.current=focus;
 useEffect(()=>{
  let live=true;
  void (async()=>{
   let value=await host?.workbenchTimers?.().catch(()=>null);
   if(!value||!live)return;
   try{
    // One-time lift of whatever the old localStorage copy still holds, so nobody loses a list.
    if(!localStorage.getItem(MIGRATED)){
     const legacy={focus:validFocus(readStore('focus',null)),todos:validTodos(readStore('todos',[])),health:validHealth(readStore('health',null))};
     const pristine=!value.todos.length&&!value.focus.completed&&!value.focus.end&&!value.health.enabled;
     if(pristine&&(legacy.todos.length||legacy.focus.completed||legacy.health.enabled||readStore('focus',null)!==null))value=await host?.workbenchTimersSet?.(legacy,true)??value;
     localStorage.setItem(MIGRATED,'1');
    }
   }catch{/* a blocked storage area must not stop the page from loading its timers */}
   if(live)setTimers(value);
  })();
  const visible=()=>{if(!document.hidden)void host?.workbenchTimers?.().then(setTimers).catch(()=>{});};
  const off=host?.workbenchTimersSubscribe?.(setTimers);
  document.addEventListener('visibilitychange',visible);
  return()=>{live=false;off?.();document.removeEventListener('visibilitychange',visible);};
 },[]);
 useEffect(()=>{
  if(!host?.workbenchTodoChange)void host?.quickToolsSync?.({focus,todos}).catch(()=>{});
 },[focus,todos]);
 useEffect(()=>host?.quickToolsSubscribe?.(({name,value})=>{
  if(name==='focus-toggle')editFocus(f=>f.end?{...f,remaining:Math.max(0,Math.ceil((f.end-Date.now())/1000)),end:null}:{...f,end:Date.now()+f.remaining*1000});
  else if(name==='focus-reset')editFocus(f=>({...f,end:null,remaining:f.duration*60,mode:'focus'}));
  else if(name==='focus-set-seconds'&&typeof value==='number'&&Number.isInteger(value)&&value>=60&&value<=10800)editFocus(f=>({...f,end:null,duration:Math.ceil(value/60),remaining:value,mode:'focus'}));
  else if(name==='todo-done'&&typeof value==='string')changeTodo({kind:'update',id:value,done:true});
  else if(name==='todo-add'&&value&&typeof value==='object'){
   const v=value as {text:string;minutes:number};
   if(typeof v.text==='string'&&v.text.trim()&&v.text.length<=200&&[0,30,60].includes(v.minutes)){
    const date=new Date(Date.now()+v.minutes*60000);
    const due=v.minutes?new Date(date.getTime()-date.getTimezoneOffset()*60000).toISOString().slice(0,16):'';
    changeTodo({kind:'add',text:v.text.trim(),due});
   }
  }
 }),[]);
 const live=useRef(true),weather=useRef(false),inFlight=useRef(false);
 const visible=useRef(!host?.workbenchVisibility&&!document.hidden),refreshPending=useRef(false);
 const refresh=useCallback(async ():Promise<void>=>{
  if(!host?.desktopSnapshot||!live.current||!visible.current)return;
  if(inFlight.current){refreshPending.current=true;return;}
  inFlight.current=true;
  try{
   do{
    refreshPending.current=false;
    try{
     const next=await host.desktopSnapshot();
     if(!live.current||!visible.current)return;
     setData(next);
     if(!weather.current){
      weather.current=true;
      if(next.city)void host.desktopAction?.({name:'weather',value:next.city}).then(refresh).catch(()=>{});
     }
    }catch(e){if(live.current&&visible.current)setError(String(e));}
   }while(refreshPending.current&&live.current&&visible.current);
  }
  finally{inFlight.current=false;}
 },[]);
 useEffect(()=>{
  live.current=true;
  if(!host?.desktopSnapshot)return;
  let subscribed=true,receivedVisibility=false;
  const updateVisibility=(isVisible:boolean)=>{visible.current=isVisible;if(isVisible)void refresh();};
  const documentVisibility=()=>updateVisibility(!document.hidden);
  const offVisibility=host.workbenchVisibilitySubscribe?.(isVisible=>{receivedVisibility=true;updateVisibility(isVisible);});
  if(host.workbenchVisibility){
   void host.workbenchVisibility().then(value=>{if(subscribed&&!receivedVisibility)updateVisibility(value);}).catch(()=>{
    if(subscribed&&!receivedVisibility)documentVisibility();
   });
  }else{
   document.addEventListener('visibilitychange',documentVisibility);
   documentVisibility();
  }
  const off=host.desktopSubscribe?.(()=>void refresh());
  return ()=>{subscribed=false;live.current=false;offVisibility?.();off?.();document.removeEventListener('visibilitychange',documentVisibility);};
 },[refresh]);
 useEffect(()=>{
  const timer=setInterval(()=>void refresh(),active?30000:120000);
  return ()=>clearInterval(timer);
 },[active,refresh]);
 async function push(patch:{focus?:Focus;todos?:Todo[];health?:Health}){
  if(!host?.workbenchTimersSet)return;
  try{setTimers(await host.workbenchTimersSet(patch));}
  catch(e){setError(e instanceof Error?e.message:String(e));}
 }
 function editFocus(updater:(value:Focus)=>Focus){void push({focus:updater(focusRef.current)});}
 function changeTodo(change:TimersTodoChange){
  if(host?.workbenchTodoChange){
   void host.workbenchTodoChange(change).then(setTimers).catch(e=>setError(e instanceof Error?e.message:String(e)));
   return;
  }
  // A renderer served by an older host can still use the original whole-list bridge.
  const list=lastTimers.current?.todos??cached.current?.todos??[];
  if(change.kind==='add'&&list.length>=200)return;
  const next=change.kind==='add'?[...list,{id:crypto.randomUUID(),text:change.text,due:change.due,done:false}]
   :change.kind==='remove'?list.filter(item=>item.id!==change.id)
    :list.map(item=>item.id===change.id?{...item,done:change.done??item.done,due:change.due??item.due}:item);
  void push({todos:next});
 }
 function setHealth(updater:(value:Health)=>Health){void push({health:updater(health)});}
 function toggleFocus(){editFocus(f=>f.end?{...f,remaining:Math.max(0,Math.ceil((f.end-Date.now())/1000)),end:null}:{...f,end:Date.now()+f.remaining*1000});}
 function resetFocus(minutes=focus.duration){const value=Number.isFinite(minutes)?Math.max(1,Math.min(180,Math.round(minutes))):focus.duration;editFocus(f=>({...f,end:null,duration:value,remaining:value*60,mode:'focus'}));}
 function setBreakDuration(minutes:number){const value=Math.max(1,Math.min(60,Math.round(minutes)));editFocus(f=>({...f,breakDuration:value}));}
 function setFocusTime(seconds:number){const limit=focus.mode==='break'?60*60:180*60;const value=Number.isFinite(seconds)?Math.max(1,Math.min(limit,Math.round(seconds))):focus.remaining;editFocus(f=>({...f,end:null,remaining:value,duration:f.mode==='focus'?Math.max(1,Math.min(180,Math.ceil(value/60))):f.duration,breakDuration:f.mode==='break'?Math.max(1,Math.min(60,Math.ceil(value/60))):f.breakDuration}));}
 async function action(name:string,value?:unknown){if(!host?.desktopAction||busy)return false;setBusy(name);setError('');try{setData(await host.desktopAction({name,value}));return true;}catch(e){setError(e instanceof Error?e.message:String(e));return false;}finally{setBusy('');}}
 return {data,error,setError,busy,action,todos,changeTodo,focus,toggleFocus,resetFocus,setBreakDuration,setFocusTime,health,setHealth,supported:!!host?.desktopSnapshot};
}
export type Workbench=ReturnType<typeof useWorkbench>;
export function formatTime(seconds:number){return Math.floor(seconds/60).toString().padStart(2,'0')+':'+Math.floor(seconds%60).toString().padStart(2,'0');}
export function weatherName(code?:number){if(code===undefined)return '等待天气';return code===0?'晴':code<=3?'多云':code<=48?'雾':code<=67?'雨':code<=77?'雪':code<=82?'阵雨':code<=86?'阵雪':'雷雨';}
