'use strict';
const path=require('node:path');
const assert=require('node:assert/strict');
const {LocalModel,ENDPOINT,MODEL}=require('../console-v2/frontend/electron/main/local-model.cjs');
const {Assistant}=require('../console-v2/frontend/electron/main/assistant.cjs');
async function main(){
  const runtime=new LocalModel({root:path.resolve(__dirname,'../local-model/qwen')});
  try{
    await runtime.ensure();
    const owned=!!runtime.child;
    const bot=new Assistant();bot.configure({value:{endpoint:ENDPOINT,model:MODEL},key:'',ensureReady:()=>runtime.ensure()});
    assert.ok((await bot.models()).models.includes(MODEL));
    const reply=await bot.chat({id:'local-qwen-check',model:MODEL,messages:[{role:'user',content:'请用一句简短的中文问好。'}]},()=>{});
    assert.ok(reply.text.length>0);console.log(JSON.stringify({endpoint:ENDPOINT,model:MODEL,owned,reply:reply.text}));
    await runtime.stop();
    if(owned){assert.equal(await runtime.ready(),false);console.log('Owned server stopped successfully.');}
  }finally{await runtime.stop();}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
