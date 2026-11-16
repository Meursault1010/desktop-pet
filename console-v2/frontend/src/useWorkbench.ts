import {useCallback,useEffect,useRef,useState} from 'react';
import {host} from './host';
import type {DesktopSnapshot,TimersSnapshot} from './host/types';
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
 function setTimers(value:TimersSnapshot|null){
  if(!value)return;
  setTimersState(value);
  try{saveStore('focus',value.focus);saveStore('todos',value.todos);saveStore('health',value.health);}catch{/* the cache is a convenience, not a source of truth */}
 }
 const {focus,todos,health}=timers??cached.current;
 const focusRef=useRef(focus),todosRef=useRef(todos);
 focusRef.current=focus;todosRef.current=todos;
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
     if(pristine&&(legacy.todos.length||legacy.focus.completed||legacy.health.enabled||readStore('focus',null)!==null))value=await host?.workbenchTimersSet?.(legacy)??value;
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
 useEffect(()=>{void host?.quickToolsSync?.({focus,todos}).catch(()=>{});},[focus,todos]);
 useEffect(()=>host?.quickToolsSubscribe?.(({name,value})=>{
  if(name==='focus-toggle')editFocus(f=>f.end?{...f,remaining:Math.max(0,Math.ceil((f.end-Date.now())/1000)),end:null}:{...f,end:Date.now()+f.remaining*1000});
  else if(name==='focus-reset')editFocus(f=>({...f,end:null,remaining:f.duration*60,mode:'focus'}));
  else if(name==='focus-set-seconds'&&typeof value==='number'&&Number.isInteger(value)&&value>=60&&value<=10800)editFocus(f=>({...f,end:null,duration:Math.ceil(value/60),remaining:value,mode:'focus'}));
  else if(name==='todo-done'&&typeof value==='string')setTodos(ts=>ts.map(t=>t.id===value?{...t,done:true}:t));
  else if(name==='todo-add'&&value&&typeof value==='object'){
   const v=value as {text:string;minutes:number};
   if(typeof v.text==='string'&&v.text.trim()&&v.text.length<=200&&[0,30,60].includes(v.minutes))setTodos(ts=>ts.length>=200?ts:[...ts,{id:crypto.randomUUID(),text:v.text.trim(),done:false,due:v.minutes?new Date(Date.now()+v.minutes*60000-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16):''}]);
  }
 }),[]);
 const live=useRef(true),weather=useRef(false),inFlight=useRef(false);
 const refresh=useCallback(async()=>{
  if(!host?.desktopSnapshot||inFlight.current)return;
  inFlight.current=true;
  try{
   const next=await host.desktopSnapshot();
   if(!live.current)return;
   setData(next);
   if(!weather.current){weather.current=true;if(next.city)void host.desktopAction?.({name:'weather',value:next.city}).then(v=>{if(live.current)setData(v);}).catch(()=>{});}
  }catch(e){if(live.current)setError(String(e));}
  finally{inFlight.current=false;}
 },[]);
 useEffect(()=>{
  live.current=true;
  if(!host?.desktopSnapshot)return;
  void refresh();
  // The main process now signals real changes; this slow tick only catches what a hidden
  // window missed while it was away.
  const timer=setInterval(()=>{if(!document.hidden)void refresh();},active?30000:120000);
  const visible=()=>{if(!document.hidden)void refresh();};
  document.addEventListener('visibilitychange',visible);
  const off=host.desktopSubscribe?.(()=>{if(!document.hidden)void refresh();});
  return ()=>{live.current=false;clearInterval(timer);off?.();document.removeEventListener('visibilitychange',visible);};
 },[active,refresh]);
 async function push(patch:{focus?:Focus;todos?:Todo[];health?:Health}){
  if(!host?.workbenchTimersSet)return;
  try{setTimers(await host.workbenchTimersSet(patch));}
  catch(e){setError(e instanceof Error?e.message:String(e));}
 }
 // Edits travel as a whole replacement and come back as the authoritative snapshot, so the
 // page never keeps a private copy of a countdown the main process may have just finished.
 function editFocus(updater:(value:Focus)=>Focus){void push({focus:updater(focusRef.current)});}
 function setTodos(updater:(list:Todo[])=>Todo[]){void push({todos:updater(todosRef.current)});}
 function setHealth(updater:(value:Health)=>Health){void push({health:updater(health)});}
 function toggleFocus(){editFocus(f=>f.end?{...f,remaining:Math.max(0,Math.ceil((f.end-Date.now())/1000)),end:null}:{...f,end:Date.now()+f.remaining*1000});}
 function resetFocus(minutes=focus.duration){const value=Number.isFinite(minutes)?Math.max(1,Math.min(180,Math.round(minutes))):focus.duration;editFocus(f=>({...f,end:null,duration:value,remaining:value*60,mode:'focus'}));}
 function setBreakDuration(minutes:number){const value=Math.max(1,Math.min(60,Math.round(minutes)));editFocus(f=>({...f,breakDuration:value}));}
 function setFocusTime(seconds:number){const limit=focus.mode==='break'?60*60:180*60;const value=Number.isFinite(seconds)?Math.max(1,Math.min(limit,Math.round(seconds))):focus.remaining;editFocus(f=>({...f,end:null,remaining:value,duration:f.mode==='focus'?Math.max(1,Math.min(180,Math.ceil(value/60))):f.duration,breakDuration:f.mode==='break'?Math.max(1,Math.min(60,Math.ceil(value/60))):f.breakDuration}));}
 async function action(name:string,value?:unknown){if(!host?.desktopAction||busy)return false;setBusy(name);setError('');try{setData(await host.desktopAction({name,value}));return true;}catch(e){setError(e instanceof Error?e.message:String(e));return false;}finally{setBusy('');}}
 return {data,error,setError,busy,action,todos,setTodos,focus,toggleFocus,resetFocus,setBreakDuration,setFocusTime,health,setHealth,supported:!!host?.desktopSnapshot};
}
export type Workbench=ReturnType<typeof useWorkbench>;
export function formatTime(seconds:number){return Math.floor(seconds/60).toString().padStart(2,'0')+':'+Math.floor(seconds%60).toString().padStart(2,'0');}
export function weatherName(code?:number){if(code===undefined)return '等待天气';return code===0?'晴':code<=3?'多云':code<=48?'雾':code<=67?'雨':code<=77?'雪':code<=82?'阵雨':code<=86?'阵雪':'雷雨';}
