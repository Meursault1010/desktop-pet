'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {LocalModel,ENDPOINT,MODEL}=require('../main/local-model.cjs');
test('reuses a ready local Qwen without spawning or stopping another process',async()=>{
  let spawned=false;
  const runtime=new LocalModel({root:'missing',fetchImpl:async url=>{assert.equal(url,ENDPOINT+'/models');return Response.json({data:[{id:MODEL}]});},spawnProcess:()=>{spawned=true;}});
  await runtime.ensure();await runtime.stop();assert.equal(spawned,false);
});
test('does not accept an unrelated model on the bundled endpoint',async()=>{
  const runtime=new LocalModel({root:'missing',fetchImpl:async()=>Response.json({data:[{id:'another-model'}]})});
  assert.equal(await runtime.ready(),false);await assert.rejects(runtime.ensure(),/缺失/);
});
test('coalesces concurrent initialization and permits retry after failure',async()=>{
  const runtime=new LocalModel({root:'missing'});let calls=0;
  runtime.start=async()=>{calls++;await new Promise(resolve=>setTimeout(resolve,5));throw Error('load failed');};
  const a=runtime.ensure(),b=runtime.ensure();assert.equal(a,b);
  await assert.rejects(a,/load failed/);await assert.rejects(runtime.ensure(),/load failed/);assert.equal(calls,2);
});
test('shutdown prevents a later lazy restart',async()=>{
  const runtime=new LocalModel({root:'missing'});await runtime.stop();await assert.rejects(runtime.ensure(),/已停止/);
});
