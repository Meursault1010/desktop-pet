import {useLayoutEffect,useMemo,useRef,useState,type CSSProperties,type KeyboardEvent} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {CalendarDays,ChevronDown,ChevronLeft,ChevronRight,ChevronUp,Clock3} from 'lucide-react';
import './TodoDateTimePicker.css';

const two=(number:number)=>String(number).padStart(2,'0');
const dateKey=(date:Date)=>`${String(date.getFullYear()).padStart(4,'0')}-${two(date.getMonth()+1)}-${two(date.getDate())}`;
const weekdays=['一','二','三','四','五','六','日'];
const mondayIndex=(date:Date)=>(date.getDay()+6)%7;
const dayOffset=(date:Date,days:number)=>new Date(date.getFullYear(),date.getMonth(),date.getDate()+days);
const monthStart=(date:Date)=>new Date(date.getFullYear(),date.getMonth(),1);
function monthOffset(date:Date,months:number){
 const month=new Date(date.getFullYear(),date.getMonth()+months,1);
 const lastDay=new Date(month.getFullYear(),month.getMonth()+1,0).getDate();
 return dayOffset(month,Math.min(date.getDate(),lastDay)-1);
}
const fullDay=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'long',day:'numeric',weekday:'long'});
const shortDay=new Intl.DateTimeFormat('zh-CN',{month:'numeric',day:'numeric'});
const monthTitle=new Intl.DateTimeFormat('zh-CN',{year:'numeric',month:'long'});
const panelWidth=322;
const panelHeight=414;

export function TodoDateTimePicker({value,onChange,label}:{
 value:string;onChange:(value:string)=>void;label:string;
}){
 const trigger=useRef<HTMLButtonElement>(null);
 const [panel,setPanel]=useState<HTMLDivElement|null>(null);
 const focusedDay=useRef<HTMLButtonElement>(null);
 const focusAfterMonth=useRef(false);
 const focusOnOpen=useRef(false);
 const [open,setOpen]=useState(false);
 const [day,setDay]=useState(()=>new Date()),[view,setView]=useState(()=>monthStart(day));
 const [cursor,setCursor]=useState(day),[direction,setDirection]=useState(0);
 const [hour,setHour]=useState(''),[minute,setMinute]=useState('');
 const [position,setPosition]=useState<{left:number;top:number;width:number;maxHeight:number;above:boolean;origin:number}|null>(null);
 const saved=value?new Date(value):null;
 const hasDate=!!saved&&!Number.isNaN(saved.getTime());
 // Keep the calendar mounted during the closing animation, but never build it
 // for every inactive reminder button in a long list.
 const calendarVisible=open||panel!==null;
 const today=calendarVisible?dateKey(new Date()):'';
 const days=useMemo(()=>{
  if(!calendarVisible)return [];
  const start=dayOffset(view,-mondayIndex(view));
  return Array.from({length:42},(_,index)=>dayOffset(start,index));
 },[calendarVisible,view]);
 const selectedKey=calendarVisible?dateKey(day):'';
 const selectedIndex=days.findIndex(date=>dateKey(date)===selectedKey);
 const validTime=hour!==''&&minute!==''&&Number(hour)<=23&&Number(minute)<=59;

 function changeOpen(next:boolean){
  if(next){
   const date=hasDate&&saved?saved:new Date();
   focusOnOpen.current=true;setPosition(null);
   setDay(date);setView(monthStart(date));setCursor(date);setDirection(0);
   setHour(two(date.getHours()));setMinute(two(date.getMinutes()));
  }
  setOpen(next);
 }
 useLayoutEffect(()=>{
  if(!open||!trigger.current||!panel)return;
  const anchor=trigger.current,content=panel;
  function place(){
   const rect=anchor.getBoundingClientRect();
   const inset=8,gap=7;
   if(rect.bottom<=inset||rect.top>=window.innerHeight-inset){setOpen(false);return;}
   const width=Math.max(0,Math.min(panelWidth,window.innerWidth-inset*2));
   const below=window.innerHeight-inset-rect.bottom-gap;
   const aboveSpace=rect.top-inset-gap;
   const needed=content.scrollHeight+2;
   const above=below<panelHeight&&aboveSpace>below;
   const maxHeight=Math.max(0,above?aboveSpace:below);
   const left=Math.max(inset,Math.min(rect.right-width,window.innerWidth-inset-width));
   const top=above?rect.top-gap-Math.min(needed,maxHeight):rect.bottom+gap;
   const origin=Math.max(12,Math.min(width-12,rect.left+rect.width/2-left));
   setPosition(previous=>previous?.left===left&&previous.top===top&&previous.width===width
    &&previous.maxHeight===maxHeight&&previous.above===above&&previous.origin===origin?previous
    :{left,top,width,maxHeight,above,origin});
  }
  place();
  const resize=new ResizeObserver(place);
  resize.observe(anchor);
  resize.observe(content);
  window.addEventListener('resize',place);
  document.addEventListener('scroll',place,true);
  return()=>{resize.disconnect();window.removeEventListener('resize',place);document.removeEventListener('scroll',place,true);};
 },[open,panel]);
 useLayoutEffect(()=>{
  if(!open||!position||!focusOnOpen.current)return;
  focusOnOpen.current=false;
  focusedDay.current?.focus({preventScroll:true});
 },[open,position]);
 useLayoutEffect(()=>{
  if(!focusAfterMonth.current)return;
  focusAfterMonth.current=false;
  focusedDay.current?.focus({preventScroll:true});
 },[cursor]);

 function moveCursor(date:Date,focus=false){
  const month=monthStart(date);
  if(dateKey(month)!==dateKey(view)){
   setDirection(Math.sign(month.getTime()-view.getTime()));
   setView(month);
  }
  focusAfterMonth.current=focus;
  setCursor(date);
 }
 function selectDate(date:Date,focus=false){setDay(date);moveCursor(date,focus);}
 function calendarKeys(event:KeyboardEvent<HTMLButtonElement>,date:Date){
  let next:Date;
  switch(event.key){
   case 'ArrowLeft':next=dayOffset(date,-1);break;
   case 'ArrowRight':next=dayOffset(date,1);break;
   case 'ArrowUp':next=dayOffset(date,-7);break;
   case 'ArrowDown':next=dayOffset(date,7);break;
   case 'Home':next=dayOffset(date,-mondayIndex(date));break;
   case 'End':next=dayOffset(date,6-mondayIndex(date));break;
   case 'PageUp':next=monthOffset(date,event.shiftKey?-12:-1);break;
   case 'PageDown':next=monthOffset(date,event.shiftKey?12:1);break;
   default:return;
  }
  event.preventDefault();
  moveCursor(next,true);
 }
 function stepTime(unit:'hour'|'minute',step:number){
  const max=unit==='hour'?24:60;
  const current=Number(unit==='hour'?hour:minute);
  (unit==='hour'?setHour:setMinute)(two(((current+step)%max+max)%max));
 }
 function commit(next:string){if(next!==value)onChange(next);setOpen(false);}
 function confirm(){
  if(!validTime)return;
  const date=`${dateKey(day)}T${two(Number(hour))}:${two(Number(minute))}`;
  commit(date);
 }

 return <Dialog.Root modal={false} open={open} onOpenChange={changeOpen}>
  <Dialog.Trigger ref={trigger} className="todo-time-trigger" type="button" aria-label={hasDate&&saved?`${label}，${fullDay.format(saved)} ${two(saved.getHours())}:${two(saved.getMinutes())}`:label}>
   <CalendarDays size={15}/><span>{hasDate&&saved?<>{shortDay.format(saved)} <b>{two(saved.getHours())}:{two(saved.getMinutes())}</b></>:'设置提醒'}</span><ChevronDown size={13} className="todo-time-chevron"/>
  </Dialog.Trigger>
  <Dialog.Portal>
   <Dialog.Content ref={setPanel} className="todo-time-panel" data-above={position?.above} data-positioned={!!position}
    data-tight={!!position&&position.maxHeight<panelHeight}
    style={{left:position?.left,top:position?.top,width:position?.width??panelWidth,maxHeight:position?.maxHeight,'--todo-origin':position?position.origin+'px':undefined} as CSSProperties}
    onOpenAutoFocus={event=>event.preventDefault()}>
    {calendarVisible&&<><header className="todo-time-heading">
     <Dialog.Title><CalendarDays size={15}/> 提醒时间</Dialog.Title>
     <Dialog.Description>选择日期和时间，到点提醒一次。</Dialog.Description>
    </header>
    <div className="todo-month-bar">
     <button type="button" className="todo-time-icon" aria-label="上个月" onClick={()=>moveCursor(monthOffset(cursor,-1))}><ChevronLeft size={16}/></button>
     <span aria-live="polite">{monthTitle.format(view)}</span>
     <button type="button" className="todo-time-icon" aria-label="下个月" onClick={()=>moveCursor(monthOffset(cursor,1))}><ChevronRight size={16}/></button>
    </div>
    <div className="todo-calendar" role="grid" aria-label={monthTitle.format(view)}>
     <div className="todo-week" role="row">{weekdays.map(label=><span key={label} role="columnheader">{label}</span>)}</div>
     <div className="todo-calendar-days" role="rowgroup" key={dateKey(view)} style={{'--todo-month-slide':direction*11+'px'} as CSSProperties}>
      {selectedIndex>=0&&<span aria-hidden="true" className="todo-date-marker" style={{'--todo-day-x':selectedIndex%7,'--todo-day-y':Math.floor(selectedIndex/7)} as CSSProperties}/>}
      {Array.from({length:6},(_,week)=><div key={week} role="row" className="todo-date-week">
       {days.slice(week*7,week*7+7).map(date=>{
        const key=dateKey(date),focus=key===dateKey(cursor),chosen=key===selectedKey;
        return <div key={key} role="gridcell" aria-selected={chosen}>
         <button ref={focus?focusedDay:undefined} type="button" className="todo-date" data-outside={date.getMonth()!==view.getMonth()}
          data-chosen={chosen} aria-label={fullDay.format(date)} aria-current={key===today?'date':undefined}
          tabIndex={focus?0:-1} onKeyDown={event=>calendarKeys(event,date)} onClick={()=>selectDate(date,true)}>{date.getDate()}</button>
        </div>;
       })}
      </div>)}
     </div>
    </div>
    <div className="todo-time-row">
     <div className="todo-quick-days"><button type="button" onClick={()=>selectDate(new Date())}>今天</button><button type="button" onClick={()=>selectDate(dayOffset(new Date(),1))}>明天</button></div>
     <div className="todo-time-fields" role="group" aria-label="具体时间"><Clock3 size={14} aria-hidden="true"/>
      {(['hour','minute'] as const).map((unit,index)=>{
       const name=unit==='hour'?'小时':'分钟',time=unit==='hour'?hour:minute,setTime=unit==='hour'?setHour:setMinute;
       return <span className="todo-time-segment" key={unit}>
        {index===1&&<span aria-hidden="true" className="todo-time-colon">:</span>}
        <input type="text" inputMode="numeric" aria-label={name} maxLength={2} value={time}
         aria-invalid={time!==''&&Number(time)>(unit==='hour'?23:59)}
         onChange={event=>setTime(event.target.value.replace(/\D/g,''))}
         onBlur={()=>{if(time!=='')setTime(two(Number(time)));}}
         onKeyDown={event=>{
          if(event.key==='ArrowUp'||event.key==='ArrowDown'){event.preventDefault();stepTime(unit,event.key==='ArrowUp'?1:-1);}
          else if(event.key==='Enter'){event.preventDefault();confirm();}
         }}/>
        <span className="todo-time-stepper">
         <button type="button" aria-label={`增加${name}`} onClick={()=>stepTime(unit,1)}><ChevronUp size={11}/></button>
         <button type="button" aria-label={`减少${name}`} onClick={()=>stepTime(unit,-1)}><ChevronDown size={11}/></button>
        </span>
       </span>;
      })}
     </div>
    </div>
    <footer className="todo-time-footer">
     <button type="button" className="todo-time-clear" disabled={!hasDate} onClick={()=>commit('')}>清除</button>
     <Dialog.Close type="button" className="button secondary">取消</Dialog.Close>
     <button type="button" className="button primary" disabled={!validTime} onClick={confirm}>确定</button>
    </footer></>}
   </Dialog.Content>
  </Dialog.Portal>
 </Dialog.Root>;
}
