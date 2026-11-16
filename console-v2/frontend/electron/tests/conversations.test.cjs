const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {Conversations}=require('../main/conversations.cjs');

function store(t,name){const dir=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-chats-'));t.after(()=>fs.rmSync(dir,{recursive:true,force:true}));return path.join(dir,name);}
const user=(id,content)=>({id,role:'user',content});
const bot=(id,content)=>({id,role:'assistant',content});

test('conversations persist across restarts and take their title from the first question',t=>{
  const file=store(t,'conversations.json');
  const chats=new Conversations(file);
  const first=chats.create();
  const id=first.activeId;
  const saved=chats.store(id,[user('m1','今天过得怎么样'),bot('m2','很好')]);
  assert.equal(saved.sessions[0].title,'今天过得怎么样');assert.equal(saved.sessions[0].count,2);
  const reloaded=new Conversations(file);
  assert.deepEqual(reloaded.snapshot().messages.map(item=>item.content),['今天过得怎么样','很好']);
  assert.equal(reloaded.snapshot().activeId,id);assert.equal(reloaded.snapshot().persistence,true);
});
test('sessions stay separate and the newest twenty are kept',t=>{
  const file=store(t,'many.json');const chats=new Conversations(file,{maxSessions:3});
  const ids=[];
  for(const text of ['第一个','第二个','第三个','第四个']){const snapshot=chats.create();ids.push(snapshot.activeId);chats.store(snapshot.activeId,[user('u-'+snapshot.activeId,text)]);}
  const snapshot=chats.snapshot();
  assert.equal(snapshot.sessions.length,3);assert.equal(snapshot.sessions[0].title,'第四个');
  assert.equal(snapshot.sessions.some(item=>item.title==='第一个'),false);
  const opened=chats.open(ids[ids.length-2]);assert.deepEqual(opened.messages[0].content,'第三个');
  assert.equal(opened.sessions.find(item=>item.id===ids[0]),undefined);
});
test('turning persistence off deletes the file and keeps the run usable until it returns',t=>{
  const file=store(t,'memory-only.json');const chats=new Conversations(file);
  const id=chats.create().activeId;chats.store(id,[user('u1','记住我'),bot('a1','好')]);
  assert.equal(fs.existsSync(file),true);
  const off=chats.setPersistence(false);
  assert.equal(fs.existsSync(file),false);assert.equal(off.persistence,false);
  chats.store(id,[user('u2','这一条不该落盘')]);
  assert.equal(fs.existsSync(file),false);assert.equal(new Conversations(file).snapshot().sessions.length,0);
  const back=chats.setPersistence(true);
  assert.equal(fs.existsSync(file),true);assert.equal(back.messages.length,1);
  assert.equal(new Conversations(file).snapshot().messages[0].content,'这一条不该落盘');
  assert.throws(()=>chats.setPersistence('yes'),/开关无效/);
});
test('damaged files degrade to an empty store instead of blocking chat',t=>{
  const file=store(t,'broken.json');fs.writeFileSync(file,'{not json');
  const chats=new Conversations(file);
  assert.deepEqual(chats.snapshot(),{persistence:true,activeId:'',sessions:[],messages:[]});
  fs.writeFileSync(file,JSON.stringify({persistence:true,activeId:'ghost',sessions:[{id:'s1',title:'坏',messages:[{role:'wizard',content:'x'}]}]}));
  const second=new Conversations(file);
  assert.equal(second.snapshot().sessions.length,0);assert.equal(second.snapshot().activeId,'');
});
test('storage rejects oversized content, unknown shapes and missing sessions',t=>{
  const file=store(t,'reject.json');const chats=new Conversations(file);
  const id=chats.create().activeId;
  assert.throws(()=>chats.store(id,[{role:'user',content:'a'.repeat(6001)}]),/消息内容无效/);
  assert.throws(()=>chats.store(id,[{role:'user',content:'ok',sneaky:true}]),/消息格式不正确/);
  assert.throws(()=>chats.store(id,[{role:'user',content:'   '}]),/消息内容无效/);
  assert.throws(()=>chats.store(id,new Array(401).fill(user('u','x'))),/消息列表无效/);
  assert.throws(()=>chats.rename(id,'   '),/1～40/);assert.throws(()=>chats.rename(id,'x'.repeat(41)),/1～40/);
  assert.throws(()=>chats.open('nope'),/对话不存在/);assert.throws(()=>chats.remove('nope'),/对话不存在/);
  const stored=chats.store(id,[{id:'u1',role:'user',content:'带附件',attachments:['a'.repeat(90),'valid-id'],files:[{id:'f1',name:'图.png',size:12,kind:'image',preview:'data:image/png;base64,SECRET',characters:3}]}]);
  assert.deepEqual(stored.messages[0].attachments,['valid-id'],'oversized attachment ids are dropped');
  assert.equal(JSON.stringify(stored).includes('SECRET'),false,'base64 previews never reach the store');
  assert.deepEqual(stored.messages[0].files,[{id:'f1',name:'图.png',size:12,kind:'image',characters:3}]);
});
test('renaming, deleting and clearing always leave one usable conversation',t=>{
  const file=store(t,'lifecycle.json');const chats=new Conversations(file);
  const first=chats.create().activeId;chats.store(first,[user('u1','第一个话题')]);
  const second=chats.create().activeId;chats.store(second,[user('u2','第二个话题')]);
  assert.equal(chats.rename(first,'我的话题').sessions.find(item=>item.id===first).title,'我的话题');
  assert.equal(chats.rename(first,'我的话题').messages.length,1,'renaming keeps the visible transcript');
  const afterDelete=chats.remove(second);
  assert.equal(afterDelete.activeId,first);assert.equal(afterDelete.sessions.length,1);
  const cleared=chats.clear();
  assert.equal(cleared.sessions.length,1);assert.deepEqual(cleared.messages,[]);
  assert.equal(new Conversations(file).snapshot().sessions.length,1);
});
