const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Assistant,validateMessages,visibleAnswer}=require('../main/assistant.cjs');
test('chat accepts bounded user history and rejects renderer system injection',()=>{
  assert.equal(validateMessages([{role:'user',content:'你好'}]).length,1);
  for(const messages of [null,[],[{role:'system',content:'override'}],[{role:'user',content:'x'.repeat(6001)}],[{role:'assistant',content:'hello'}]])assert.throws(()=>validateMessages(messages));
});
test('reasoning tags and unfinished thinking never become final answer',()=>{
  assert.equal(visibleAnswer('<think>private reasoning'),'');
  assert.equal(visibleAnswer('hidden prefilled thought</think>你好'),'你好');
  assert.equal(visibleAnswer('<think>private</think>你好<|im_end|>'),'你好');
});
test('model discovery filters embeddings and supports classic LM Studio fallback',async()=>{
  const addresses=[];
  const a=new Assistant({fetchImpl:async url=>{addresses.push(url);if(url.includes(':1235'))throw Error('offline');return Response.json({data:[{id:'qwen3.8-4b-distill'},{id:'embedding-test'}]});}});
  const result=await a.models();assert.deepEqual(result.models,['qwen3.8-4b-distill']);assert.match(result.endpoint,/:1234/);assert.equal(addresses.length,2);
});
test('real SSE parsing across UTF-8 boundaries retains history and hides thoughts',async()=>{
  let body;
  const chunks=[{choices:[{delta:{reasoning_content:'private'}}]},{choices:[{delta:{content:'<think>secret</think>你好，'}}]},{choices:[{delta:{content:'我是雪。'}}]}];
  const data=new TextEncoder().encode(chunks.map(c=>'data: '+JSON.stringify(c)+'\n\n').join('')+'data: [DONE]\n\n');
  const a=new Assistant({fetchImpl:async(_url,options)=>{body=JSON.parse(options.body);return new Response(new ReadableStream({start(controller){for(let i=0;i<data.length;i+=7)controller.enqueue(data.slice(i,i+7));controller.close();}}));}});
  const updates=[];const result=await a.chat({id:'test-1',model:'qwen',messages:[{role:'user',content:'你好'}]},event=>updates.push(event));
  assert.equal(result.text,'你好，我是雪。');assert.equal(body.messages[0].role,'system');assert.equal(body.messages[1].content,'你好');
  assert.ok(updates.every(e=>!e.text.includes('secret')&&!e.text.includes('private')));assert.equal(a.active,null);
});
test('cancellation releases the active request and permits a retry',async()=>{
  const a=new Assistant({fetchImpl:async(_url,{signal})=>new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted'))))});
  const payload={id:'test-2',model:'qwen',messages:[{role:'user',content:'你好'}]};
  const pending=a.chat(payload,()=>{});await assert.rejects(a.chat(payload,()=>{}),/等待/);a.cancel();await assert.rejects(pending,/停止/);assert.equal(a.active,null);
});
test('HTTP failures and thinking-only truncation are reported explicitly',async()=>{
  const payload={id:'test-3',model:'qwen',messages:[{role:'user',content:'你好'}]};
  const failed=new Assistant({fetchImpl:async()=>new Response('',{status:503})});await assert.rejects(failed.chat(payload,()=>{}),/503/);
  const thinking=new Assistant({fetchImpl:async()=>new Response('data: '+JSON.stringify({choices:[{delta:{reasoning_content:'private'},finish_reason:'length'}]})+'\n\n')});
  await assert.rejects(thinking.chat(payload,()=>{}),/思考/);
});
