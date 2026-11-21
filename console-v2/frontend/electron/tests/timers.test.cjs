'use strict';
// The clock and the scheduler are injected, so every case below moves time without waiting.
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {WorkbenchTimers}=require('../main/workbench-timers.cjs');

const START=1_800_000_000_000;

function fixture(t,overrides={}) {
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-timers-'));
  t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));
  let clock=START;
  const notes=[],scheduled=[];
  const service=new WorkbenchTimers({
    file:path.join(dir,'workbench-timers.json'),
    notify:text=>notes.push(text),
    now:()=>clock,
    setTimeoutImpl:(fn,ms)=>{const item={fn,ms};scheduled.push(item);return item;},
    clearTimeoutImpl:item=>{const index=scheduled.indexOf(item);if(index>=0)scheduled.splice(index,1);},
    ...overrides,
  });
  const at=value=>{clock=value;return service;};
  const advanceTo=value=>{clock=value;return service.advance();};
  return {dir,service,notes,scheduled,at,advanceTo,clock:()=>clock};
}

test('a focus session completes once, counts itself and hands over to the break',t=>{
  const {service,notes,scheduled,advanceTo}=fixture(t);
  service.apply({focus:{mode:'focus',duration:25,breakDuration:5,end:START+60000,remaining:60}});
  assert.equal(scheduled.length,1,'one wake-up is scheduled for the nearest deadline');
  assert.equal(scheduled[0].ms,60050);
  const fired=advanceTo(START+60001);
  assert.equal(fired.length,1);
  assert.match(fired[0].text,/这段专注完成了。休息5分钟/);
  assert.equal(service.focus.completed,1);
  assert.equal(service.focus.mode,'break');
  assert.equal(service.focus.end,null);
  assert.equal(service.focus.remaining,300);
  assert.deepEqual(notes,[fired[0].text]);
  // Nothing is left to fire, so the same deadline never repeats.
  assert.deepEqual(advanceTo(START+70000),[]);
  assert.equal(service.focus.completed,1);
});

test('todo reminders fire once each and a stale patch cannot re-arm them',t=>{
  const {service,notes,at,advanceTo}=fixture(t);
  const due=new Date(START+1000).toISOString();
  service.apply({todos:[{id:'a',text:'交周报',due,done:false},{id:'b',text:'买牛奶',due:'',done:false}]});
  const first=advanceTo(START+1001);
  assert.equal(first.length,1);
  assert.equal(first[0].text,'待办提醒：交周报');
  assert.deepEqual(notes,['待办提醒：交周报']);
  assert.deepEqual(advanceTo(START+2000),[]);
  // The renderer keeps editing the whole list; the fired flag survives because the time is unchanged.
  const next=service.apply({todos:[{id:'a',text:'交周报',due,done:false},{id:'b',text:'买牛奶',due:'',done:true}]});
  assert.equal(next.todos.find(item=>item.id==='a').notified,true);
  assert.deepEqual(advanceTo(START+3000),[]);
  // Moving the deadline is a fresh intent and re-arms the reminder.
  service.apply({todos:[{id:'a',text:'交周报',due:new Date(START+9000).toISOString(),done:false}]});
  assert.equal(service.todos.find(item=>item.id==='a').notified,false);
  assert.equal(advanceTo(START+9001)[0].text,'待办提醒：交周报');
  assert.deepEqual(at(START+9500).advance(),[],'and it fires exactly once');
});

test('rest reminders stay quiet during a focus session and resume right after it',t=>{
  const {service,advanceTo}=fixture(t);
  service.apply({health:{enabled:true,minutes:50,next:START+5000}});
  service.apply({focus:{mode:'focus',duration:1,breakDuration:5,end:START+20000,remaining:60}});
  assert.deepEqual(advanceTo(START+6000),[],'no rest nag while the timer is running');
  assert.equal(service.health.next,START+5000);
  const fired=advanceTo(START+20001);
  assert.deepEqual(fired.map(event=>event.kind),['focus','rest'],'the handover and the overdue rest both land');
  assert.equal(service.health.next,START+20001+50*60000);
});

test('waking from sleep never replays missed reminders, but a finished session still counts',t=>{
  const {service,notes,at}=fixture(t);
  service.apply({todos:[{id:'a',text:'取快递',due:new Date(START+60000).toISOString(),done:false}]});
  service.apply({health:{enabled:true,minutes:50,next:START+120000}});
  service.apply({focus:{mode:'focus',duration:1,breakDuration:5,end:START+180000,remaining:60}});
  service.suspend();
  const fired=at(START+600000).wake({silent:true});
  assert.equal(fired.length,1,'only the focus session speaks up');
  assert.equal(fired[0].kind,'focus');
  assert.equal(service.todos[0].notified,true,'the missed todo is marked spent in silence');
  assert.ok(service.health.next>START+600000,'the missed rest is pushed out without a nag');
  assert.deepEqual(notes,[fired[0].text]);
  assert.equal(at(START+600001).advance().length,0,'nothing fires twice on the way back');
});

test('a restart keeps absolute deadlines and continues by the real clock',t=>{
  const {dir,service}=fixture(t);
  service.apply({todos:[{id:'a',text:'接孩子',due:new Date(START+3600000).toISOString(),done:false}]});
  service.apply({focus:{mode:'focus',duration:25,breakDuration:5,end:START+7200000,remaining:1500}});
  const reopened=new WorkbenchTimers({file:path.join(dir,'workbench-timers.json'),notify:()=>{},now:()=>START+7200001,setTimeoutImpl:()=>({}),clearTimeoutImpl:()=>{}});
  assert.equal(reopened.todos.length,1,'the list survives the restart');
  assert.equal(reopened.todos[0].due,new Date(START+3600000).toISOString());
  assert.deepEqual(reopened.advance().map(event=>event.kind).sort(),['focus','todo'],'an elapsed session and an overdue todo are both caught once');
  assert.equal(reopened.focus.completed,1);
  assert.equal(reopened.focus.end,null);
  assert.deepEqual(reopened.advance(),[],'and neither of them repeats');
});

test('only one wake-up is armed at a time and it always points at the nearest deadline',t=>{
  const {service,scheduled}=fixture(t);
  service.apply({todos:[{id:'far',text:'远',due:new Date(START+90000).toISOString(),done:false}]});
  assert.equal(scheduled[0].ms,90050);
  service.apply({todos:[{id:'far',text:'远',due:new Date(START+90000).toISOString(),done:false},{id:'near',text:'近',due:new Date(START+5000).toISOString(),done:false}]});
  assert.equal(scheduled.length,1,'re-arming replaces the old timer');
  assert.equal(scheduled[0].ms,5050);
  service.apply({todos:[],health:{enabled:false}});
  const midnight=new Date(START);
  midnight.setHours(24,0,0,0);
  assert.equal(scheduled.length,1,'only the daily reset remains scheduled');
  assert.equal(scheduled[0].ms,midnight.getTime()-START+50);
});

test('individual todo edits keep other rows and only a changed deadline re-arms a reminder',t=>{
  const {service,advanceTo}=fixture(t);
  const due=new Date(START+1000).toISOString();
  const a=service.changeTodo({kind:'add',text:'交周报',due}).todos[0];
  const b=service.changeTodo({kind:'add',text:'买牛奶',due:''}).todos[1];
  advanceTo(START+1001);
  const updated=service.changeTodo({kind:'update',id:b.id,done:true});
  assert.deepEqual(updated.todos.map(item=>[item.id,item.done,item.notified]),[[a.id,false,true],[b.id,true,false]]);
  const newDue=new Date(START+3000).toISOString();
  const rescheduled=service.changeTodo({kind:'update',id:a.id,due:newDue});
  assert.equal(rescheduled.todos[0].notified,false);
  assert.equal(rescheduled.todos[1].done,true);
  assert.equal(advanceTo(START+3001).length,1);
});

test('bad patches are rejected and out-of-range numbers fall back',t=>{
  const {service}=fixture(t);
  assert.throws(()=>service.apply({focus:{},extra:1}),/计时状态无效/);
  assert.throws(()=>service.apply({todos:'nope'}),/待办列表无效/);
  assert.throws(()=>service.apply({todos:[{id:'a',text:'   ',due:'',done:false}]}),/待办内容不能为空/);
  // The sliders must not be able to poison the store, so nonsense numbers fall back silently.
  const safe=service.apply({focus:{duration:9999,breakDuration:-4,completed:-2},health:{minutes:0,enabled:'yes'}});
  assert.equal(safe.focus.duration,25);
  assert.equal(safe.focus.breakDuration,5);
  assert.equal(safe.focus.completed,0);
  assert.equal(safe.health.minutes,50);
  assert.equal(safe.health.enabled,false);
  const clamped=service.apply({focus:{end:START+9999999999}});
  assert.equal(clamped.focus.end,START+21600000,'a far future end is clamped to six hours');
});
