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

test('stop terminates owned inference and resume can start again',async()=>{
  const {EventEmitter}=require('node:events');
  const runtime=new LocalModel({root:'missing'});
  const child=new EventEmitter();let killed=false;
  child.kill=()=>{killed=true;queueMicrotask(()=>{runtime.child=null;child.emit('close',0);});};
  runtime.child=child;await runtime.stop();assert.equal(killed,true);
  await assert.rejects(runtime.ensure());
  let starts=0;runtime.start=async()=>{starts++;};
  await runtime.resume();assert.equal(starts,1);assert.equal(runtime.stopped,false);
});
test('builtin preference defaults off, persists, and survives endpoint saves',()=>{
  const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
  const {ModelConfig}=require('../main/model-config.cjs');
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-builtin-'));
  try{
    const file=path.join(dir,'model.json'),storage={isEncryptionAvailable:()=>false};
    const config=new ModelConfig(file,storage);
    assert.equal(config.snapshot().builtinEnabled,false);
    config.setBuiltinEnabled(true);config.set({endpoint:ENDPOINT,model:MODEL});
    assert.equal(new ModelConfig(file,storage).snapshot().builtinEnabled,true);
    config.setBuiltinEnabled(false);
    assert.equal(new ModelConfig(file,storage).snapshot().builtinEnabled,false);
    assert.throws(()=>config.setBuiltinEnabled('false'));
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
