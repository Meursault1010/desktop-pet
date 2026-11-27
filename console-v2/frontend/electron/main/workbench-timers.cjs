'use strict';
// Focus, todos and health reminders used to be driven from the renderer, so closing the
// workbench window stopped the clock and clearing browser storage deleted the data. This
// module owns the deadlines instead: absolute timestamps, one scheduled wake-up for the
// nearest one, and reminders delivered through the self-drawn desktop notification window.
const fs=require('node:fs');
const path=require('node:path');
const {randomUUID}=require('node:crypto');

const MAX_TODOS=200,MAX_TEXT=200,MAX_FOCUS=180,MAX_BREAK=60,MAX_HEALTH=240,MAX_END_AHEAD=21600000;

function bounded(value,min,max,fallback){return Number.isFinite(value)&&Math.round(value)>=min&&Math.round(value)<=max?Math.round(value):fallback;}
function localDateKey(timestamp){const value=new Date(timestamp);return `${value.getFullYear()}-${String(value.getMonth()+1).padStart(2,'0')}-${String(value.getDate()).padStart(2,'0')}`;}
function nextLocalMidnight(timestamp){const value=new Date(timestamp);value.setHours(24,0,0,0);return value.getTime();}

function focusValue(input,previous,now){
  const merged={...previous,...(input&&typeof input==='object'&&!Array.isArray(input)?input:{})};
  const duration=bounded(merged.duration,1,MAX_FOCUS,previous.duration);
  const breakDuration=bounded(merged.breakDuration,1,MAX_BREAK,previous.breakDuration);
  const mode=merged.mode==='break'?'break':'focus';
  const end=Number.isFinite(merged.end)&&merged.end>0?Math.round(Math.min(merged.end,now+MAX_END_AHEAD)):null;
  const limit=(mode==='break'?breakDuration:duration)*60;
  const today=localDateKey(now),completed=merged.completedDate===today&&Number.isFinite(merged.completed)?Math.max(0,Math.floor(merged.completed)):0;
  return {duration,breakDuration,mode,end,
    completed,completedDate:today,
    remaining:Number.isFinite(merged.remaining)?Math.max(0,Math.min(limit,Math.round(merged.remaining))):limit};
}

function normalizeTodo(item,previous){
  if(!item||typeof item!=='object'||Array.isArray(item))throw new Error('待办事项无效');
  const text=typeof item.text==='string'?item.text.replace(/\s+/g,' ').trim().slice(0,MAX_TEXT):'';
  if(!text)throw new Error('待办内容不能为空');
  const id=typeof item.id==='string'&&item.id?item.id.slice(0,80):randomUUID();
  const due=typeof item.due==='string'&&Number.isFinite(Date.parse(item.due))?item.due:'';
  return {id,text,due,done:item.done===true,notified:!!(previous?.due===due&&previous.notified===true)};
}

// Whole-list inputs are retained for migration and old callers. Only the store
// marks reminders as spent, and a changed deadline is a fresh reminder.
function todoValue(list,previous,{loading=false}={}){
  if(!Array.isArray(list))throw new Error('待办列表无效');
  const known=new Map(previous.map(item=>[item.id,item]));
  return list.slice(0,MAX_TODOS).map(item=>{
    const id=typeof item?.id==='string'?item.id.slice(0,80):null;
    return normalizeTodo(item,loading?item:known.get(id));
  });
}

function changeTodoList(list,change){
  if(!change||typeof change!=='object'||Array.isArray(change))throw new Error('待办操作无效');
  const validKeys=keys=>Object.keys(change).every(key=>keys.includes(key));
  if(change.kind==='add'&&validKeys(['kind','text','due'])
      &&typeof change.text==='string'&&change.text.length<=MAX_TEXT&&typeof change.due==='string'&&change.due.length<=40){
    if(list.length>=MAX_TODOS)throw new Error('待办已满，请在工作台清理已完成条目');
    return [...list,normalizeTodo({text:change.text,due:change.due})];
  }
  if(typeof change.id!=='string'||!change.id||change.id.length>160)throw new Error('待办编号无效');
  const index=list.findIndex(item=>item.id===change.id);
  if(change.kind==='remove'&&validKeys(['kind','id']))return index===-1?list:list.filter((_,i)=>i!==index);
  if(change.kind==='update'&&validKeys(['kind','id','done','due'])
      &&(change.done!==undefined||change.due!==undefined)
      &&(change.done===undefined||typeof change.done==='boolean')
      &&(change.due===undefined||typeof change.due==='string'&&change.due.length<=40)){
    if(index===-1)return list;
    const before=list[index];
    const next=normalizeTodo({...before,done:change.done??before.done,due:change.due??before.due},before);
    if(next.due===before.due&&next.done===before.done)return list;
    return list.map((item,i)=>i===index?next:item);
  }
  throw new Error('待办操作无效');
}

function healthValue(input,previous){
  const merged={...previous,...(input&&typeof input==='object'&&!Array.isArray(input)?input:{})};
  return {enabled:merged.enabled===true,minutes:bounded(merged.minutes,1,MAX_HEALTH,previous.minutes),
    next:Number.isFinite(merged.next)&&merged.next>0?Math.round(merged.next):0};
}

class WorkbenchTimers {
  constructor({file,notify=()=>{},changed=()=>{},powerMonitor=null,log=()=>{},now=Date.now,
    setTimeoutImpl=(fn,ms)=>setTimeout(fn,ms),clearTimeoutImpl=timer=>clearTimeout(timer)}={}) {
    Object.assign(this,{file,notify,changed,powerMonitor,log,now,setTimeoutImpl,clearTimeoutImpl});
    this.focus={end:null,remaining:1500,duration:25,breakDuration:5,completed:0,completedDate:localDateKey(this.now()),mode:'focus'};
    this.todos=[];this.health={enabled:false,minutes:50,next:0};
    this.timer=null;this.paused=false;this.history=[];this.listening=[];this.revision=0;
    this.load();
  }
  load(){
    if(!this.file)return;
    let saved=null;
    try{saved=JSON.parse(fs.readFileSync(this.file,'utf8'));}catch{return;}
    if(!saved||typeof saved!=='object'||Array.isArray(saved))return;
    const now=this.now();
    const today=localDateKey(now),savedFocus=saved.focus&&typeof saved.focus==='object'?saved.focus:{};
    this.focus=focusValue({...savedFocus,completed:savedFocus.completedDate===today?savedFocus.completed:0,completedDate:today},this.focus,now);
    try{this.todos=todoValue(Array.isArray(saved.todos)?saved.todos:[],[],{loading:true});}catch{this.todos=[];}
    this.health=healthValue(saved.health,this.health);
  }
  save(){
    if(!this.file)return;
    try{
      fs.mkdirSync(path.dirname(this.file),{recursive:true});
      const temp=this.file+'.tmp';
      fs.writeFileSync(temp,JSON.stringify({focus:this.focus,todos:this.todos,health:this.health}));
      fs.renameSync(temp,this.file);
    }catch(error){this.log('计时状态写入失败：'+String(error.message||error));}
  }
  rollFocusDay(now=this.now()){
    const today=localDateKey(now);
    if(this.focus.completedDate===today)return false;
    this.focus={...this.focus,completed:0,completedDate:today};
    return true;
  }
  snapshot(){const now=this.now();if(this.rollFocusDay(now))this.save();return {focus:{...this.focus},todos:this.todos.map(item=>({...item})),health:{...this.health},serverTime:now,revision:++this.revision};}
  changeTodo(change){
    const next=changeTodoList(this.todos,change);
    if(next===this.todos)return this.snapshot();
    this.todos=next;
    this.rollFocusDay();
    this.save();
    this.arm();
    const value=this.snapshot();
    this.changed(value);
    return value;
  }
  apply(input){
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(key=>!['focus','todos','health'].includes(key)))throw new Error('计时状态无效');
    const now=this.now();
    this.rollFocusDay(now);
    if(input.focus!==undefined){const focusPatch={...input.focus};if(typeof focusPatch.completedDate!=='string'){focusPatch.completed=this.focus.completed;focusPatch.completedDate=this.focus.completedDate;}this.focus=focusValue(focusPatch,this.focus,now);}
    if(input.todos!==undefined)this.todos=todoValue(input.todos,this.todos);
    if(input.health!==undefined)this.health=healthValue(input.health,this.health);
    this.save();this.arm();
    return this.snapshot();
  }
  // A rest deadline is only interesting while no focus session is running; leaving it out
  // keeps the scheduled wake-up from firing every 50ms on a `next` we deliberately ignore.
  nextDeadline(){
    const at=[nextLocalMidnight(this.now())];
    if(this.focus.end)at.push(this.focus.end);
    for(const item of this.todos)if(!item.done&&!item.notified&&item.due){const due=Date.parse(item.due);if(Number.isFinite(due))at.push(due);}
    if(!this.focus.end&&this.health.enabled&&this.health.next)at.push(this.health.next);
    return at.filter(value=>Number.isFinite(value)).sort((a,b)=>a-b)[0]??null;
  }
  arm(){
    if(this.timer){this.clearTimeoutImpl(this.timer);this.timer=null;}
    if(this.paused)return;
    const next=this.nextDeadline();
    if(next===null)return;
    this.timer=this.setTimeoutImpl(()=>{this.timer=null;this.advance();this.arm();},Math.max(0,next-this.now())+50);
  }
  advance(){
    const now=this.now(),fired=[],dayChanged=this.rollFocusDay(now);
    if(this.focus.end&&now>=this.focus.end){
      const focusEnded=this.focus.mode==='focus',breakMinutes=this.focus.breakDuration;
      this.focus={...this.focus,end:null,mode:focusEnded?'break':'focus',
        remaining:(focusEnded?breakMinutes:this.focus.duration)*60,
        completed:this.focus.completed+(focusEnded?1:0)};
      fired.push({kind:'focus',at:now,text:focusEnded?`这段专注完成了。休息${breakMinutes}分钟，再继续吧。`:'休息结束，准备开始下一段专注吧。'});
    }
    const due=this.todos.filter(item=>!item.done&&!item.notified&&item.due&&Date.parse(item.due)<=now);
    if(due.length){
      due.forEach(item=>{item.notified=true;});
      fired.push({kind:'todo',at:now,text:'待办提醒：'+due.map(item=>item.text).join('、')});
    }
    if(this.health.enabled&&this.health.next&&now>=this.health.next&&!this.focus.end){
      this.health={...this.health,next:now+this.health.minutes*60000};
      fired.push({kind:'rest',at:now,text:'休息一下，喝点水，看看远处。雪陪你缓一缓。'});
    }
    if(fired.length){this.save();this.deliver(fired);}
    else if(dayChanged){this.save();this.changed();}
    return fired;
  }
  deliver(fired){
    fired.forEach(event=>{
      this.history=[event,...this.history].slice(0,20);
      try{this.notify(event.text,event.kind);}
      catch(error){this.log('提醒发送失败：'+String(error.message||error));}
    });
    try{this.changed();}catch(error){this.log('计时状态通知失败：'+String(error.message||error));}
  }
  suspend(){this.paused=true;if(this.timer){this.clearTimeoutImpl(this.timer);this.timer=null;}}
  // Coming back from sleep never replays what was missed: todo and rest deadlines are
  // marked spent in silence. A focus session still completes, because it counts as done.
  wake({silent=false}={}){
    const now=this.now();let dirty=false;
    if(silent){
      this.todos.forEach(item=>{if(!item.done&&!item.notified&&item.due&&Date.parse(item.due)<=now){item.notified=true;dirty=true;}});
      if(this.health.next&&this.health.next<=now){this.health={...this.health,next:now+this.health.minutes*60000};dirty=true;}
      // Silent bookkeeping still has to reach the page, or it keeps showing a reminder as pending.
      if(dirty){this.save();this.changed();}
    }
    this.paused=false;
    const fired=this.advance();
    this.arm();
    return fired;
  }
  start(){
    if(!this.powerMonitor?.on||this.listening.length)return;
    const on=(name,fn)=>{this.powerMonitor.on(name,fn);this.listening.push([name,fn]);};
    on('suspend',()=>this.suspend());
    on('resume',()=>this.wake({silent:true}));
  }
  stop(){
    if(this.timer)this.clearTimeoutImpl(this.timer);
    this.timer=null;
    this.listening.forEach(([name,fn])=>this.powerMonitor?.removeListener?.(name,fn));
    this.listening=[];
  }
}

module.exports={WorkbenchTimers,focusValue,todoValue,healthValue};
