const {test}=require('node:test');
const assert=require('node:assert/strict');
const {QuickChat}=require('../main/quick-chat.cjs');
const {validate}=require('../shared/protocol.cjs');

test('quick chat selects model, streams in order and retains bounded conversation',async()=>{
  const events=[],requests=[];
  const assistant={models:async()=>({models:['other','qwen3.8-4b']}),chat:async(payload,emit)=>{
    requests.push(payload);emit({phase:'answer',text:'你好'});return {text:'你好，我是雪。'};
  }};
  const chat=new QuickChat(assistant,async event=>events.push(event));
  await chat.run('one','你好');await chat.run('two','你叫什么？');
  assert.equal(requests[0].model,'qwen3.8-4b');
  assert.equal(requests[1].messages[1].role,'assistant');
  assert.equal(events.at(-1).phase,'done');
  assert.equal(events.at(-1).text,'你好，我是雪。');
  assert.ok(events.filter(e=>e.phase==='answer').length);
  assert.equal(chat.busy,false);
});

test('quick chat respects workbench model and handles offline and busy',async()=>{
  const events=[];
  const assistant={preferredModel:'chosen',models:async()=>({models:['chosen','qwen3.8-4b']}),
    chat:async payload=>{assert.equal(payload.model,'chosen');return {text:'收到'};}};
  const chat=new QuickChat(assistant,async event=>events.push(event));
  await chat.run('one','你好');
  assistant.active={};await chat.run('two','你好');
  assert.equal(events.at(-1).phase,'error');
  assistant.active=null;assistant.models=async()=>{throw Error('未连接 LM Studio');};
  await chat.run('three','你好');assert.match(events.at(-1).text,/LM Studio/);
  assert.equal(chat.history.length,2);
  assert.equal(chat.busy,false);
});

test('quick chat disconnect during discovery cannot start inference or deliver stale updates',async()=>{
  let resolve;const events=[];
  const assistant={models:()=>new Promise(r=>resolve=r),chat:()=>{throw Error('should not run');},cancel:()=>{}};
  const chat=new QuickChat(assistant,async event=>events.push(event));
  const request=chat.run('one','你好');await Promise.resolve();
  chat.cancel();resolve({models:['qwen']});await request;
  assert.equal(events.length,1);assert.equal(chat.history.length,0);assert.equal(chat.busy,false);
});

test('speech protocol rejects oversized, injected and malformed updates',()=>{
  assert.doesNotThrow(()=>validate('speech_update',{id:'one',phase:'done',text:'你好'}));
  for(const payload of [
    {id:'../bad',phase:'done',text:'x'}, {id:'one',phase:'system',text:'x'},
    {id:'one',phase:'done',text:'x'.repeat(6001)}, {id:'one',phase:'done',text:'x',path:'secret'}
  ])assert.throws(()=>validate('speech_update',payload));
});
