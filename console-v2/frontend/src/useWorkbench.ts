import {useCallback,useEffect,useRef,useState} from 'react';
import {host} from './host';
import type {DesktopSnapshot} from './host/types';
import {readStore,saveStore,validTodos,validFocus,validHealth,type Focus,type Todo} from './workspaceModel';
const empty:DesktopSnapshot={clipboard:[],clipboardPaused:false,media:{available:false},battery:{available:false},events:[],weather:null,city:'',inbox:''};
export function useWorkbench(active=true){
 const [data,setData]=useState(empty),[error,setError]=useState(''),[busy,setBusy]=useState('');
 const [todos,setTodos]=useState<Todo[]>(()=>validTodos(readStore('todos',[])));
 const [focus,setFocus]=useState<Focus>(()=>validFocus(readStore('focus',null)));
 useEffect(()=>{void host?.quickToolsSync?.({focus,todos}).catch(()=>{});},[focus,todos]);
 useEffect(()=>host?.quickToolsSubscribe?.(({name,value})=>{
  if(name==='focus-toggle')setFocus(f=>f.end?{...f,remaining:Math.max(0,Math.ceil((f.end-Date.now())/1000)),end:null}:{...f,end:Date.now()+f.remaining*1000});
  else if(name==='focus-reset')setFocus(f=>({...f,end:null,remaining:f.duration*60,mode:'focus'}));
  else if(name==='todo-done'&&typeof value==='string')setTodos(ts=>ts.map(t=>t.id===value?{...t,done:true}:t));
  else if(name==='todo-add'&&value&&typeof value==='object'){
   const v=value as {text:string;minutes:number};
   if(typeof v.text==='string'&&v.text.trim()&&v.text.length<=200&&[0,30,60].includes(v.minutes))setTodos(ts=>ts.length>=200?ts:[...ts,{id:crypto.randomUUID(),text:v.text.trim(),done:false,due:v.minutes?new Date(Date.now()+v.minutes*60000-new Date().getTimezoneOffset()*60000).toISOString().slice(0,16):''}]);
  }
 }),[]);
 const [health,setHealth]=useState(()=>validHealth(readStore('health',null)));
 const [reminder,setReminder]=useState(''),[storageError,setStorageError]=useState('');
 const live=useRef(true),weather=useRef(false),inFlight=useRef(false);
 const refresh=useCallback(async()=>{
  if(!host?.desktopSnapshot||inFlight.current)return;
  inFlight.current=true;
  try{
   const next=await host.desktopSnapshot();
   if(!live.current)return;
   setData(next);
   if(!weather.current&&next.city){weather.current=true;void host.desktopAction?.({name:'weather',value:next.city}).then(v=>{if(live.current)setData(v);}).catch(()=>{});}
  }catch(e){if(live.current)setError(String(e));}
  finally{inFlight.current=false;}
 },[]);
 useEffect(()=>{
  live.current=true;
  if(!host?.desktopSnapshot)return;
  void refresh();
  const timer=setInterval(()=>{if(!document.hidden)void refresh();},active?3000:15000);
  const visible=()=>{if(!document.hidden)void refresh();};
  document.addEventListener('visibilitychange',visible);
  const off=host.desktopSubscribe?.(()=>{if(!document.hidden)void refresh();});
  return ()=>{live.current=false;clearInterval(timer);off?.();document.removeEventListener('visibilitychange',visible);};
 },[active,refresh]);
 useEffect(()=>{try{saveStore('todos',todos);saveStore('focus',focus);saveStore('health',health);setStorageError('');}catch{setStorageError('本地存储不可用，当前修改仅在本次窗口中保留。');}},[todos,focus,health]);
 const notify=useCallback((message:string)=>{setReminder(message);void host?.desktopAction?.({name:'notify',value:message}).catch(()=>{});},[]);
 const focusRef=useRef(focus),todosRef=useRef(todos),healthRef=useRef(health);
 focusRef.current=focus;todosRef.current=todos;healthRef.current=health;
 useEffect(()=>{
  const timer=setInterval(()=>{
   const now=Date.now(),current=focusRef.current;
   if(current.end&&now>=current.end){
    const focusEnded=current.mode==='focus';
    setFocus(f=>({...f,end:null,remaining:focusEnded?300:f.duration*60,mode:focusEnded?'break':'focus',completed:f.completed+(focusEnded?1:0)}));
    notify(focusEnded?'这段专注完成了。休息五分钟，再继续吧。':'休息结束，准备开始下一段专注吧。');
   }
   const due=todosRef.current.filter(t=>!t.done&&!t.notified&&t.due&&new Date(t.due).getTime()<=now);
   if(due.length){setTodos(ts=>ts.map(t=>due.some(d=>d.id===t.id)?{...t,notified:true}:t));notify('待办提醒：'+due.map(t=>t.text).join('、'));}
   const rest=healthRef.current;
   if(rest.enabled&&rest.next&&now>=rest.next&&!focusRef.current.end){setHealth(h=>({...h,next:now+h.minutes*60000}));notify('休息一下，喝点水，看看远处。雪陪你缓一缓。');}
  },1000);
  return ()=>clearInterval(timer);
 },[notify]);
 async function action(name:string,value?:unknown){if(!host?.desktopAction||busy)return false;setBusy(name);setError('');try{setData(await host.desktopAction({name,value}));return true;}catch(e){setError(e instanceof Error?e.message:String(e));return false;}finally{setBusy('');}}
 function toggleFocus(){setFocus(f=>f.end?{...f,remaining:Math.max(0,Math.ceil((f.end-Date.now())/1000)),end:null}:{...f,end:Date.now()+f.remaining*1000});}
 function resetFocus(minutes=focus.duration){setFocus(f=>({...f,end:null,duration:minutes,remaining:minutes*60,mode:'focus'}));}
 return {data,error,setError,busy,action,todos,setTodos,focus,toggleFocus,resetFocus,health,setHealth,reminder,setReminder,storageError,supported:!!host?.desktopSnapshot};
}
export type Workbench=ReturnType<typeof useWorkbench>;
export function formatTime(seconds:number){return Math.floor(seconds/60).toString().padStart(2,'0')+':'+Math.floor(seconds%60).toString().padStart(2,'0');}
export function weatherName(code?:number){if(code===undefined)return '等待天气';return code===0?'晴':code<=3?'多云':code<=48?'雾':code<=67?'雨':code<=77?'雪':code<=82?'阵雨':code<=86?'阵雪':'雷雨';}
