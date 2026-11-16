'use strict';
// Focused end-to-end check for OPT-07: the clock now runs in the main process, so a reminder
// has to reach the desktop even when the workbench window is closed. It runs on its own
// because the legacy smoke still asserts the old nine-page layout.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));

async function run({app,window,timers,desktopReminders,notifyWindow,sidecar,stopAndQuit}) {
  const results=[],errors=[],started=Date.now();
  const capture=async (target,name)=>{
    if(!process.env.YUKI_UI_CAPTURE_DIR||!target||target.isDestroyed())return;
    const folder=path.resolve(process.env.YUKI_UI_CAPTURE_DIR);fs.mkdirSync(folder,{recursive:true});
    fs.writeFileSync(path.join(folder,name+'.png'),(await target.webContents.capturePage()).toPNG());
  };
  const waitFor=async (label,done,limit=120)=>{for(let i=0;i<limit;i++){if(await done())return;await wait(100);}throw new Error('Timed out: '+label);};
  async function check(name,task){try{await task();results.push(name);console.log('PASS '+name);}catch(error){errors.push(name+' → '+(error.message||error));console.log('FAIL '+name+': '+(error.message||error));}};

  await check('the workbench window can close without stopping the clock',async()=>{
    window.hide();
    assert.equal(window.isVisible(),false,'the workbench really is closed for this check');
    const before=desktopReminders.length;
    timers.apply({todos:[{id:'smoke-hidden',text:'关掉工作台也要提醒我',due:new Date(Date.now()+1200).toISOString(),done:false}]});
    await waitFor('a todo reminder while hidden',()=>Promise.resolve(desktopReminders.length>before));
    const latest=desktopReminders.at(-1);
    assert.match(latest.text,/关掉工作台也要提醒我/);
    assert.equal(latest.shown,true,'the self-drawn desktop card is what showed, not the system fallback');
    const card=notifyWindow();
    assert.ok(card&&!card.isDestroyed()&&card.isVisible(),'the notification window is on screen');
    await capture(card,'timers-card-while-hidden');
    assert.equal(timers.todos[0].notified,true,'the fired reminder is marked spent in the store');
    assert.deepEqual(timers.advance(),[],'and it never fires twice');
  });

  await check('a focus session ending while hidden counts once and hands over to the break',async()=>{
    const before=desktopReminders.length,completed=timers.snapshot().focus.completed;
    timers.apply({focus:{...timers.snapshot().focus,mode:'focus',duration:1,breakDuration:5,end:Date.now()+1200,remaining:60}});
    await waitFor('the focus handover',()=>Promise.resolve(desktopReminders.length>before));
    assert.match(desktopReminders.at(-1).text,/这段专注完成了。休息5分钟/);
    const after=timers.snapshot().focus;
    assert.equal(after.completed,completed+1);
    assert.equal(after.mode,'break');
    assert.equal(after.end,null);
    assert.equal(after.remaining,300);
    await wait(1500);
    assert.equal(timers.snapshot().focus.completed,completed+1,'the same session never counts twice');
  });

  await check('timers survive a hidden window and a reopened window in sync',async()=>{
    window.showInactive();
    await waitFor('the workbench to come back',()=>window.webContents.executeJavaScript(`document.visibilityState==='visible'`));
    await wait(600);
    await capture(window,'timers-workbench');
    // The overview counts completed sessions straight off the main-process snapshot.
    assert.equal(await window.webContents.executeJavaScript(`document.querySelector('.journal-metric strong')?.textContent`),String(timers.snapshot().focus.completed));
    const stored=await window.webContents.executeJavaScript(`(async()=>JSON.stringify(await window.yukiHost.workbenchTimers()))()`).then(JSON.parse);
    assert.equal(stored.focus.completed,timers.snapshot().focus.completed,'the page reads the same authority the main process fired from');
    assert.equal(stored.todos[0].id,'smoke-hidden');
    assert.equal(stored.todos[0].notified,true);
    // Editing from the page must land in the same store, not a private copy.
    await window.webContents.executeJavaScript(`window.yukiHost.workbenchTimersSet({todos:[{id:'smoke-edit',text:'页面里改的',due:'',done:false}]})`);
    await waitFor('the main store to take the edit',()=>Promise.resolve(timers.todos[0]?.id==='smoke-edit'));
    assert.equal(timers.todos[0].text,'页面里改的');
  });

  await check('the store keeps absolute deadlines a fresh instance can resume',async()=>{
    const file=path.join(app.getPath('userData'),'workbench-timers.json');
    assert.ok(fs.existsSync(file),'a running timer is written to disk');
    const saved=JSON.parse(fs.readFileSync(file,'utf8'));
    assert.ok(Array.isArray(saved.todos)&&saved.todos.length===1);
    assert.equal(typeof saved.focus.completed,'number');
    const {WorkbenchTimers}=require('./workbench-timers.cjs');
    const reopened=new WorkbenchTimers({file,notify:()=>{}});
    assert.equal(reopened.todos[0].id,'smoke-edit','a restart reads the same list back');
    assert.equal(reopened.focus.completed,saved.focus.completed);
    assert.ok(reopened.snapshot().serverTime>0);
  });

  assert.deepEqual(errors,[],'timer smoke failures');
  await sidecar.stop();
  const output={passed:results.length,results,errors,durationMs:Date.now()-started,renderer:'timers smoke'};
  console.log(JSON.stringify(output));
  await stopAndQuit();
}
module.exports={run};
