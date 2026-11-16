// Split the AI-assistant smoke checks out of smoke.cjs so they can run on their own:
// the legacy UI checks in the middle of smoke.cjs still assert the old nine-page layout,
// which used to stop the run before the model checks were ever reached.
'use strict';
const fs=require('node:fs');
const assert=require('node:assert/strict');
const path=require('node:path');
const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
async function run({app,window,sidecar,stopAndQuit}) {
  const results=[],errors=[],started=Date.now();
  const ui=code=>window.webContents.executeJavaScript(code);
  async function check(name,task,timeout=90000){let timer;try{await Promise.race([task(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error('Timed out: '+name)),timeout);})]);results.push(name);console.log('PASS '+name);}finally{clearTimeout(timer);}}
  window.webContents.on('console-message',event=>{if(event.level==='error'&&!/Content Security Policy|Refused to connect|Failed to fetch/.test(event.message)){errors.push(event.message);console.log('RENDERER ERROR '+event.message);}});
  const capture=async name=>{
    if(!process.env.YUKI_UI_CAPTURE_DIR)return;
    const folder=path.resolve(process.env.YUKI_UI_CAPTURE_DIR);fs.mkdirSync(folder,{recursive:true});
    await ui(`document.documentElement.dataset.motion='reduced'`);await wait(400);
    fs.writeFileSync(path.join(folder,name+'.png'),(await window.webContents.capturePage()).toPNG());
  };
  const navigate=async label=>{await ui(`[...document.querySelectorAll('nav button')].find(b=>b.getAttribute('aria-label')===${JSON.stringify(label)}).click()`);await wait(220);};
  await check('workbench is up and the assistant page is open',async()=>{
    for(let i=0;i<300;i++){
      if(await ui(`document.querySelector('.nav-foot').textContent.includes('桌宠已连接')`))break;
      await wait(100);
    }
    assert.ok(await ui(`document.querySelector('.nav-foot').textContent.includes('桌宠已连接')`),'backend never connected');
    window.showInactive();
    await navigate('AI 助手');
    assert.ok(await ui(`!!document.querySelector('textarea[aria-label="对话输入"]')`),'chat composer missing');
  });
    const ask=async text=>{
      await ui(`(()=>{const input=document.querySelector('textarea[aria-label="对话输入"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,${JSON.stringify(text)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      await wait(150);await ui(`document.querySelector('button[aria-label="发送消息"]').click()`);
      for(let i=0;i<850;i++){
        await wait(100);
        if(await ui(`!document.querySelector('button[aria-label="停止回复"]')`)){
          const failure=await ui(`document.querySelector('.chat-error')?.textContent||''`);assert.equal(failure,'');
          return ui(`(()=>{const body=[...document.querySelectorAll('.chat-turn.assistant')].at(-1)?.querySelector('.chat-body');return body?body.textContent:'';})()`);
        }
      }throw new Error('Local model reply timed out');
    };
    await check('local model discovery through guarded Electron IPC',async()=>{
      const result=await ui('window.yukiHost.aiModels()');assert.ok(result.models.some(id=>id.includes('qwen3.8')));
      for(let i=0;i<30;i++){if(await ui(`!!document.querySelector('#ai-model')?.value`))return;await wait(100);}throw Error('No selected model');
    });
    await check('real React chat receives a Chinese persona response',async()=>{
      const answer=await ask('你好，你叫什么名字？用一句话介绍你自己。');assert.match(answer,/雪|yuki/i);assert.doesNotMatch(answer,/<think>/);await capture('ai-real-conversation');
    },90000);
    await check('multi-turn chat remembers information in current conversation',async()=>{
      const answer=await ask('我给你准备了一杯茉莉花茶，请记住这个茶名，并用一句话回应。');assert.match(answer,/茉莉/);
    },90000);
    await check('chat survives page navigation and recalls the tea',async()=>{
      await navigate('角色');await navigate('AI 助手');await wait(300);
      assert.equal(await ui(`document.querySelectorAll('.chat-turn').length`),4);
      const answer=await ask('刚刚我给你准备的是什么茶？只回答茶名。');assert.match(answer,/茉莉/);await capture('ai-memory');
    },90000);
    await check('stop generation returns the chat to an editable state',async()=>{
      await ui(`(()=>{const input=document.querySelector('textarea[aria-label="对话输入"]');Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(input,'请详细介绍你喜欢的十种茶。');input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
      for(let i=0;i<30;i++){if(await ui(`!!document.querySelector('button[aria-label="发送消息"]:not(:disabled)')`))break;await wait(50);}
      assert.ok(await ui(`!!document.querySelector('button[aria-label="发送消息"]:not(:disabled)')`),'the send button never became ready after typing');
      await ui(`document.querySelector('button[aria-label="发送消息"]').click()`);
      // The fake model keeps streaming for about a second, so wait for the stop button instead of guessing.
      let streaming=false;
      for(let i=0;i<40;i++){if(await ui(`!!document.querySelector('button[aria-label="停止回复"]')`)){streaming=true;break;}await wait(50);}
      assert.ok(streaming,'the reply never entered the streaming state, so there was nothing to stop');
      await ui(`document.querySelector('button[aria-label="停止回复"]').click()`);
      // The composer stays editable while yuki writes; what has to come back is an enabled send button.
      const released=()=>ui(`!document.querySelector('button[aria-label="停止回复"]')&&!!document.querySelector('button[aria-label="发送消息"]:not(:disabled)')`);
      const state=()=>ui(`JSON.stringify({stop:!!document.querySelector('button[aria-label="停止回复"]'),send:document.querySelector('button[aria-label="发送消息"]')?.disabled??'missing',draft:(document.querySelector('textarea[aria-label="对话输入"]')?.value||'').slice(0,12),error:(document.querySelector('.chat-error')?.textContent||'').slice(0,60),turns:document.querySelectorAll('.chat-turn').length})`);
      for(let i=0;i<100;i++){if(await released())break;await wait(100);}
      assert.ok(await released(),'cancellation did not release composer: '+await state());
      assert.equal(await ui(`document.querySelector('textarea[aria-label="对话输入"]').value`),'请详细介绍你喜欢的十种茶。','stopping puts the question back in the composer: '+await state());
    });
    await check('the running chat is written to the conversation file and listed in the rail',async()=>{
      const file=path.join(app.getPath('userData'),'conversations.json');
      assert.ok(fs.existsSync(file),'persistence is on by default, so the file should exist');
      const saved=JSON.parse(fs.readFileSync(file,'utf8')),active=saved.sessions.find(item=>item.id===saved.activeId);
      assert.ok(active.messages.length>=3,'the turns from the checks above survive on disk');
      assert.equal(active.title,active.messages.find(item=>item.role==='user').content.slice(0,40));
      assert.ok(await ui(`[...document.querySelectorAll('.chat-session button')].some(button=>button.textContent.includes('你好，你叫什么名字'))`));
    });
    await check('markdown answers render as blocks and cannot inject markup',async()=>{
      // The fake model answers this prompt with headings, lists, a code fence and a poisoned link,
      // so the whole reply travels the real send path before it reaches the renderer.
      const answer=await ask('用 Markdown 给我一个清单');assert.match(answer,/计划/);
      const last='.chat-turn.assistant';
      assert.equal(await ui(`document.querySelector('.chat-body .md-heading')?.textContent`),'计划');
      assert.equal(await ui(`document.querySelectorAll('.chat-body .md-list li').length`),2);
      assert.equal(await ui(`document.querySelector('.chat-body .md-code')?.textContent`),'const a = 1;');
      assert.equal(await ui(`document.querySelectorAll('.chat-body a[href^="https://example.com"]').length`),1,'only the clean link is clickable');
      assert.equal(await ui(`document.querySelectorAll('.chat-body a[href^="javascript"]').length`),0);
      assert.equal(await ui(`[...document.scripts].filter(node=>node.textContent.includes('alert(1)')).length`),0,'the payload never becomes a script');
      assert.ok((await ui(`[...document.querySelectorAll('${last}')].at(-1)?.querySelector('.chat-body').textContent`)).includes('<script>alert(1)</script>'));
      await capture('ai-markdown-answer');
    },90000);
    await check('message actions edit the stored session',async()=>{
      const file=path.join(app.getPath('userData'),'conversations.json');
      const active=()=>{const saved=JSON.parse(fs.readFileSync(file,'utf8'));return saved.sessions.find(item=>item.id===saved.activeId).messages.length;};
      const before=await ui(`document.querySelectorAll('.chat-turn').length`);
      assert.equal(active(),before,'the transcript on screen matches the stored file');
      assert.ok(await ui(`!!document.querySelector('button[aria-label="复制这条消息"]')`),'every turn keeps a copy action');
      await ui(`[...document.querySelectorAll('.chat-turn')].at(-1).querySelector('button[aria-label="删除这条消息"]').click()`);
      await wait(400);
      assert.equal(await ui(`document.querySelectorAll('.chat-turn').length`),before-1);
      assert.equal(active(),before-1,'deleting a turn is written back to the store');
      assert.equal(await ui(`!![...document.querySelectorAll('.chat-turn')].at(-1).querySelector('button[aria-label="重新生成这条回答"]')`),false,'a user turn offers no regeneration');
    });
  assert.deepEqual(errors,[],'renderer console errors');
  await sidecar.stop();
  const output={passed:results.length,results,consoleErrors:errors,durationMs:Date.now()-started,versions:process.versions,renderer:'AI smoke'};
  const target=process.env.YUKI_SMOKE_REPORT;
  if(target){fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,JSON.stringify(output,null,2));}
  console.log(JSON.stringify(output));await stopAndQuit();
}
module.exports={run};
