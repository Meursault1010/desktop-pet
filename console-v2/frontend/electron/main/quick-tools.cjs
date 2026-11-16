'use strict';
// Native popup is a projection of existing workbench state, never a second store.
function validateWorkbench(value){
  if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(k=>!['focus','todos'].includes(k)))throw Error('快捷工具状态无效');
  const {focus,todos}=value;
  // The focus field accepts any whole minute from 1 to 180, so the projection must not
  // recognise only the four preset buttons; that silently killed the desktop popup.
  if(!focus||!['focus','break'].includes(focus.mode)||!Number.isInteger(focus.duration)||focus.duration<1||focus.duration>180||
    !(focus.end===null||(Number.isFinite(focus.end)&&focus.end>0))||!Number.isFinite(focus.remaining)||focus.remaining<0||focus.remaining>10800||
    !Number.isInteger(focus.completed)||focus.completed<0||!Array.isArray(todos)||todos.length>200)throw Error('快捷工具状态无效');
  if(todos.some(t=>!t||typeof t.id!=='string'||t.id.length>160||typeof t.text!=='string'||t.text.length>200||typeof t.done!=='boolean'||typeof t.due!=='string'||t.due.length>40))throw Error('待办状态无效');
  return {focus:{mode:focus.mode,duration:focus.duration,end:focus.end,remaining:focus.remaining,completed:focus.completed},todos:todos.map(t=>({id:t.id,text:t.text,done:t.done,due:t.due}))};
}
function project(desktop,work,error=''){
  const pending=(work?.todos||[]).filter(t=>!t.done).sort((a,b)=>(Date.parse(a.due)||Infinity)-(Date.parse(b.due)||Infinity));
  return {ready:!!work,clipboard:desktop.clipboard.slice(0,10).map(e=>({id:e.id,text:e.preview.slice(0,240),at:e.at})),clipboardPaused:desktop.clipboardPaused,
    focus:work?.focus||null,todos:pending.slice(0,5),todoCount:pending.length,error:String(error).slice(0,200)};
}
function validateAction(name,value){
  if(['snapshot','focus-toggle','focus-reset'].includes(name)&&value==null)return;
  if(name==='focus-set-seconds'&&Number.isInteger(value)&&value>=60&&value<=10800)return;
  if(name==='clipboard-pause'&&typeof value==='boolean')return;
  if(['clipboard-copy','todo-done'].includes(name)&&typeof value==='string'&&value.length>0&&value.length<=160)return;
  if(name==='todo-add'&&value&&typeof value.text==='string'&&value.text.trim()&&value.text.length<=200&&[0,30,60].includes(value.minutes)&&Object.keys(value).every(k=>['text','minutes'].includes(k)))return;
  throw Error('快捷操作无效');
}
class QuickTools{
  constructor({desktop,deliver,forward,timers=()=>null}){Object.assign(this,{desktop,deliver,forward,timers});this.work=null;}
  async sync(value){this.work=validateWorkbench(value);await this.publish();}
  async publish(error=''){return this.deliver(project(this.desktop.snapshot(),this.work,error));}
  applyFocus(name,value){
    const timers=typeof this.timers==='function'?this.timers():this.timers;
    if(!timers)throw Error('计时器正在连接，请稍后重试');
    const {focus}=timers.snapshot(),now=timers.now();let next;
    if(name==='focus-toggle')next=focus.end?{...focus,remaining:Math.max(0,Math.ceil((focus.end-now)/1000)),end:null}:{...focus,end:now+focus.remaining*1000};
    else if(name==='focus-reset')next={...focus,end:null,remaining:focus.duration*60,mode:'focus'};
    else if(name==='focus-set-seconds')next={...focus,end:null,duration:Math.ceil(value/60),remaining:value,mode:'focus'};
    else return false;
    timers.apply({focus:next});
    timers.changed();
    if(this.work)this.work={...this.work,focus:timers.snapshot().focus};
    return true;
  }
  async action(name,value){
    try{
      validateAction(name,value);
      if(name==='snapshot')return await this.publish();
      if(name.startsWith('clipboard-')){await this.desktop.action({name,value});return await this.publish();}
      if(name.startsWith('focus-')){this.applyFocus(name,value);return await this.publish();}
      if(!this.work)throw Error('工作台正在连接，请稍后重试');
      if(name==='todo-add'&&this.work.todos.length>=200)throw Error('待办已满，请在工作台清理已完成条目');
      this.forward({name,value});
    }catch(e){await this.publish(e.message);}
  }
}
module.exports={QuickTools,validateWorkbench,validateAction,project};
