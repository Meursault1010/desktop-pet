'use strict';
// Conversation storage for the workbench chat. The renderer stays the editor and
// pushes the whole message list after each change; this module is only the store.
const fs=require('node:fs');
const path=require('node:path');
const {randomUUID}=require('node:crypto');

const MAX_SESSIONS=20,MAX_MESSAGES=400,MAX_CONTENT=6000,MAX_TITLE=40,MAX_CONVERSATION_PAYLOAD=16_000_000;
const ID=/^[a-zA-Z0-9-]{1,80}$/;

function message(input){
  if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(key=>!['id','role','content','attachments','files'].includes(key)))throw new Error('消息格式不正确');
  if(!['user','assistant'].includes(input.role))throw new Error('消息角色无效');
  if(typeof input.content!=='string'||!input.content.trim()||input.content.length>MAX_CONTENT)throw new Error('消息内容无效');
  const attachments=Array.isArray(input.attachments)?input.attachments.filter(id=>typeof id==='string'&&ID.test(id)).slice(0,4):undefined;
  // Base64 previews would bloat the file; only the label is kept, so a reloaded
  // image chip shows its name without a thumbnail.
  const files=Array.isArray(input.files)?input.files.slice(0,4).filter(item=>item&&typeof item==='object').map(item=>({id:String(item.id||'').slice(0,80),name:String(item.name||'').slice(0,160),size:Number(item.size)||0,kind:item.kind==='image'?'image':'document',characters:Number(item.characters)||0})):undefined;
  const next={id:typeof input.id==='string'&&ID.test(input.id)?input.id:randomUUID(),role:input.role,content:input.content};
  if(attachments?.length)next.attachments=attachments;
  if(files?.length)next.files=files;
  return next;
}
function derivedTitle(messages){
  const first=messages.find(item=>item.role==='user');
  const text=String(first?.content||'').replace(/\s+/g,' ').trim();
  return (text||'新对话').slice(0,MAX_TITLE);
}

class Conversations {
  constructor(file,{maxSessions=MAX_SESSIONS,log=()=>{},asyncStorage=false}={}){
    Object.assign(this,{file,maxSessions,log,asyncStorage});
    this.persistence=true;this.activeId='';this.sessions=[];this.pending=Promise.resolve();
    if(!asyncStorage)this.load();
  }
  static async loadAsync(file,options){
    const store=new Conversations(file,{...options,asyncStorage:true});
    let saved;
    try{saved=JSON.parse(await fs.promises.readFile(file,'utf8'));}catch{return store;}
    store.restore(saved);
    return store;
  }
  load(){
    let saved;
    try{saved=JSON.parse(fs.readFileSync(this.file,'utf8'));}catch{return;}
    this.restore(saved);
  }
  restore(saved){
    if(!saved||typeof saved!=='object'||Array.isArray(saved))return;
    this.persistence=saved.persistence!==false;
    this.sessions=(Array.isArray(saved.sessions)?saved.sessions:[]).slice(0,this.maxSessions).filter(item=>item&&typeof item==='object').map(item=>{
      let messages=[];
      try{messages=(Array.isArray(item.messages)?item.messages:[]).slice(-MAX_MESSAGES).map(message);}catch{return null;}
      return {id:String(item.id||'').slice(0,80)||randomUUID(),title:String(item.title||'').slice(0,MAX_TITLE)||derivedTitle(messages),updatedAt:Number(item.updatedAt)||Date.now(),messages};
    }).filter(Boolean);
    const wanted=String(saved.activeId||'');
    this.activeId=this.sessions.some(item=>item.id===wanted)?wanted:(this.sessions[0]?.id||'');
  }
  save(draft,remove){
    if(!draft.persistence){
      if(remove){
        try{fs.rmSync(this.file,{force:true});}catch(error){this.log('会话文件清理失败：'+String(error.message||error));}
      }
      return;
    }
    const temporary=`${this.file}.${process.pid}.${randomUUID()}.tmp`;
    try{
      fs.mkdirSync(path.dirname(this.file),{recursive:true});
      fs.writeFileSync(temporary,JSON.stringify(draft));
      fs.renameSync(temporary,this.file);
    }catch(error){
      try{fs.rmSync(temporary,{force:true});}catch{}
      throw this.writeError(error);
    }
  }
  async saveAsync(draft,remove){
    if(!draft.persistence){
      if(remove){
        try{await fs.promises.rm(this.file,{force:true});}catch(error){this.log('会话文件清理失败：'+String(error.message||error));}
      }
      return;
    }
    const temporary=`${this.file}.${process.pid}.${randomUUID()}.tmp`;
    try{
      await fs.promises.mkdir(path.dirname(this.file),{recursive:true});
      await fs.promises.writeFile(temporary,JSON.stringify(draft));
      await fs.promises.rename(temporary,this.file);
    }catch(error){
      try{await fs.promises.rm(temporary,{force:true});}catch{}
      throw this.writeError(error);
    }
  }
  writeError(error){
    this.log('会话写入失败：'+String(error.message||error));
    return new Error('对话记录没有保存成功，请检查磁盘空间后重试。',{cause:error});
  }
  update(change,{remove=false}={}){
    const prepare=()=>{
      const draft={persistence:this.persistence,activeId:this.activeId,sessions:this.sessions.map(session=>({...session}))};
      change(draft);
      return draft;
    };
    const commit=draft=>{Object.assign(this,draft);return this.snapshot();};
    if(!this.asyncStorage){
      const draft=prepare();
      this.save(draft,remove);
      return commit(draft);
    }
    // Serialize complete changes, including privacy toggles. A failed write
    // cannot roll back a later mutation or expose an unsaved draft as current.
    const operation=this.pending.then(async()=>{
      const draft=prepare();
      await this.saveAsync(draft,remove);
      return commit(draft);
    });
    this.pending=operation.then(()=>{},()=>{});
    return operation;
  }
  async flush(){
    let pending;
    do{pending=this.pending;await pending;}while(pending!==this.pending);
  }
  find(id,sessions=this.sessions){return sessions.find(item=>item.id===id);}
  snapshot(){const active=this.find(this.activeId);return {persistence:this.persistence,activeId:this.activeId,sessions:this.sessions.map(item=>({id:item.id,title:item.title,updatedAt:item.updatedAt,count:item.messages.length})),messages:active?active.messages:[]};}
  addSession(draft,id=randomUUID()){
    const session={id,title:'新对话',updatedAt:Date.now(),messages:[]};
    draft.activeId=id;
    draft.sessions.unshift(session);
    draft.sessions=draft.sessions.slice(0,this.maxSessions);
    return session;
  }
  requireSession(draft,id){
    const session=this.find(typeof id==='string'?id:'',draft.sessions);
    if(!session)throw new Error('对话不存在');
    return session;
  }
  create(){return this.update(draft=>{this.addSession(draft);});}
  open(id){return this.update(draft=>{draft.activeId=this.requireSession(draft,id).id;});}
  rename(id,value){
    return this.update(draft=>{
      const session=this.requireSession(draft,id);
      const name=typeof value==='string'?value.replace(/\s+/g,' ').trim():'';
      if(!name||name.length>MAX_TITLE)throw new Error('标题应为 1～40 个字符');
      session.title=name;
    });
  }
  remove(id){
    return this.update(draft=>{
      const session=this.requireSession(draft,id);
      draft.sessions=draft.sessions.filter(item=>item!==session);
      if(draft.activeId===session.id)draft.activeId=draft.sessions[0]?.id||'';
      if(!draft.sessions.length)this.addSession(draft);
    });
  }
  store(id,messages,input={id,messages}){
    if(JSON.stringify(input).length>MAX_CONVERSATION_PAYLOAD)throw new Error('这段对话已达到本机保存上限，请新建对话后继续。');
    if(!Array.isArray(messages)||messages.length>MAX_MESSAGES)throw new Error('消息列表无效');
    const normalized=messages.map(message);
    const key=typeof id==='string'&&ID.test(id)?id:undefined;
    return this.update(draft=>{
      const session=this.find(key,draft.sessions)||this.addSession(draft,key);
      session.messages=normalized;
      if(!session.title||session.title==='新对话')session.title=derivedTitle(session.messages);
      session.updatedAt=Date.now();
      draft.activeId=session.id;
    });
  }
  clear(){return this.update(draft=>{draft.sessions=[];this.addSession(draft);});}
  setPersistence(enabled){
    if(typeof enabled!=='boolean')throw new Error('会话保存开关无效');
    return this.update(draft=>{draft.persistence=enabled;},{remove:!enabled});
  }
}
module.exports={Conversations,conversationMessage:message,MAX_CONVERSATION_PAYLOAD};
