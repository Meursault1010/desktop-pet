const {test}=require('node:test');
const assert=require('node:assert/strict');
const {Assistant,validateMessages,visibleAnswer}=require('../main/assistant.cjs');
test('trusted local-time context follows shared daily schedule',()=>{
  const {routineContext}=require('../main/assistant.cjs');
  for(const [hour,name] of [[0,'夜间休息'],[6,'夜间休息'],[7,'晨起梳洗'],[9,'日间阅读'],[12,'午餐与小憩'],[13,'午间熟睡'],[14,'午后茶与活动'],[18,'晚餐与放松'],[21,'睡前放松'],[23,'夜间休息']]){
    assert.ok(routineContext(new Date(2026,0,1,hour)).includes(name));
  }
  assert.match(routineContext(new Date(2026,0,1,23,15)),/23:15/);
});
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
test('configured cloud model remains usable when provider omits model discovery',async()=>{
  const a=new Assistant({fetchImpl:async url=>{
    if(url.endsWith('/models'))return new Response('',{status:404});
    return new Response('data: '+JSON.stringify({choices:[{delta:{content:'你好'}}]})+'\n\ndata: [DONE]\n\n');
  }});
  a.configure({value:{endpoint:'https://gateway.example/v1',model:'provider-model'},key:'test-key'});
  const result=await a.models();
  assert.deepEqual(result.models,['provider-model']);
  assert.equal((await a.chat({id:'cloud-fallback',model:'provider-model',messages:[{role:'user',content:'你好'}]},()=>{})).text,'你好');
});
test('real SSE parsing across UTF-8 boundaries retains history and hides thoughts',async()=>{
  let body;
  const chunks=[{choices:[{delta:{reasoning_content:'private'}}]},{choices:[{delta:{content:'<think>secret</think>你好，'}}]},{choices:[{delta:{content:'我是雪。'}}]}];
  const data=new TextEncoder().encode(chunks.map(c=>'data: '+JSON.stringify(c)+'\n\n').join('')+'data: [DONE]\n\n');
  const a=new Assistant({fetchImpl:async(_url,options)=>{body=JSON.parse(options.body);return new Response(new ReadableStream({start(controller){for(let i=0;i<data.length;i+=7)controller.enqueue(data.slice(i,i+7));controller.close();}}));}});
  const updates=[];const result=await a.chat({id:'test-1',model:'qwen',messages:[{role:'user',content:'你好'}]},event=>updates.push(event));
  assert.equal(result.text,'你好，我是雪。');assert.equal(body.messages[0].role,'system');assert.equal(body.messages[1].content,'你好');
  assert.match(body.messages[0].content,/当前用户设备本地时间/);
  assert.ok(updates.every(e=>!e.text.includes('secret')&&!e.text.includes('private')));assert.equal(a.active,null);
});
test('cancellation releases the active request and permits a retry',async()=>{
  const a=new Assistant({fetchImpl:async(_url,{signal})=>new Promise((_,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted'))))});
  const payload={id:'test-2',model:'qwen',messages:[{role:'user',content:'你好'}]};
  const pending=a.chat(payload,()=>{});await assert.rejects(a.chat(payload,()=>{}),/等待/);a.cancel();await assert.rejects(pending,/停止/);assert.equal(a.active,null);
});

test('cloud chat sends standard OpenAI fields and configured credentials',async()=>{
  let request;
  const a=new Assistant({fetchImpl:async(url,options)=>{
    request={url,...options,body:JSON.parse(options.body)};
    return new Response('data: '+JSON.stringify({choices:[{delta:{content:'你好'}}]})+'\n\ndata: [DONE]\n\n');
  }});
  a.configure({value:{endpoint:'https://models.example/v1',model:'cloud-model'},key:'test-only-key'});
  assert.equal((await a.chat({id:'cloud-1',model:'cloud-model',messages:[{role:'user',content:'你好'}]},()=>{})).text,'你好');
  assert.equal(request.url,'https://models.example/v1/chat/completions');
  assert.equal(request.headers.Authorization,'Bearer test-only-key');
  assert.equal(request.body.model,'cloud-model');
  assert.equal(request.body.stream,true);
  assert.ok(!('top_k' in request.body));
  assert.ok(!('chat_template_kwargs' in request.body));
});
test('cloud reasoning effort is sent only when explicitly selected',async()=>{
  let body;
  const a=new Assistant({fetchImpl:async(_url,options)=>{body=JSON.parse(options.body);return new Response('data: '+JSON.stringify({choices:[{delta:{content:'认真回答'}}]})+'\n\ndata: [DONE]\n\n');}});
  a.configure({value:{endpoint:'https://models.example/v1',model:'reasoning-model',reasoningEffort:'high'},key:'test-only-key'});
  await a.chat({id:'cloud-reasoning',model:'reasoning-model',messages:[{role:'user',content:'请认真分析'}]},()=>{});
  assert.equal(body.reasoning_effort,'high');
  a.configure({value:{endpoint:'http://127.0.0.1:1235/v1',model:'local',reasoningEffort:'high'},key:''});
  await a.chat({id:'local-reasoning',model:'local',messages:[{role:'user',content:'你好'}]},()=>{});
  assert.equal(body.reasoning_effort,undefined);
});
test('HTTP failures and thinking-only truncation are reported explicitly',async()=>{
  const payload={id:'test-3',model:'qwen',messages:[{role:'user',content:'你好'}]};
  const failed=new Assistant({fetchImpl:async()=>new Response('',{status:503})});await assert.rejects(failed.chat(payload,()=>{}),/503/);
  const thinking=new Assistant({fetchImpl:async()=>new Response('data: '+JSON.stringify({choices:[{delta:{reasoning_content:'private'},finish_reason:'length'}]})+'\n\n')});
  await assert.rejects(thinking.chat(payload,()=>{}),/思考/);
});
