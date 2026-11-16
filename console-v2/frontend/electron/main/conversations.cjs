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
  constructor(file,{maxSessions=MAX_SESSIONS,log}={}){Object.assign(this,{file,maxSessions,log:log||(()=>{})});this.persistence=true;this.activeId='';this.sessions=[];this.load();}
  load(){
    let saved=null;
    try{saved=JSON.parse(fs.readFileSync(this.file,'utf8'));}catch{return;}
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
  save(){
    if(!this.persistence)return;
    const directory=path.dirname(this.file);
    const temporary=`${this.file}.${process.pid}.${randomUUID()}.tmp`;
    try{
      fs.mkdirSync(directory,{recursive:true});
      fs.writeFileSync(temporary,JSON.stringify({persistence:this.persistence,activeId:this.activeId,sessions:this.sessions}));
      fs.renameSync(temporary,this.file);
    }catch(error){
      try{fs.rmSync(temporary,{force:true});}catch{}
      this.log('会话写入失败：'+String(error.message||error));
      throw new Error('对话记录没有保存成功，请检查磁盘空间后重试。',{cause:error});
    }
  }
  find(id){return this.sessions.find(item=>item.id===id);}
  snapshot(){const active=this.find(this.activeId);return {persistence:this.persistence,activeId:this.activeId,sessions:this.sessions.map(item=>({id:item.id,title:item.title,updatedAt:item.updatedAt,count:item.messages.length})),messages:active?active.messages:[]};}
  create(){this.activeId=randomUUID();this.sessions.unshift({id:this.activeId,title:'新对话',updatedAt:Date.now(),messages:[]});this.trim();this.save();return this.snapshot();}
  open(id){const session=this.find(typeof id==='string'?id:'');if(!session)throw new Error('对话不存在');this.activeId=session.id;this.save();return this.snapshot();}
  rename(id,value){const session=this.find(typeof id==='string'?id:'');if(!session)throw new Error('对话不存在');const name=typeof value==='string'?value.replace(/\s+/g,' ').trim():'';if(!name||name.length>MAX_TITLE)throw new Error('标题应为 1～40 个字符');session.title=name;this.save();return this.snapshot();}
  remove(id){
    const session=this.find(typeof id==='string'?id:'');if(!session)throw new Error('对话不存在');
    this.sessions=this.sessions.filter(item=>item!==session);
    if(this.activeId===session.id)this.activeId=this.sessions[0]?.id||'';
    if(!this.sessions.length)this.create();else this.save();
    return this.snapshot();
  }
  store(id,messages){
    if(!Array.isArray(messages)||messages.length>MAX_MESSAGES)throw new Error('消息列表无效');
    if(JSON.stringify({id,messages}).length>MAX_CONVERSATION_PAYLOAD)throw new Error('这段对话已达到本机保存上限，请新建对话后继续。');
    let session=this.find(typeof id==='string'&&ID.test(id)?id:'');
    const previousSessions=this.sessions.slice();
    const previousActive=this.activeId;
    const previousSession=session?{...session}:null;
    if(!session){session={id:typeof id==='string'&&ID.test(id)?id:randomUUID(),title:'新对话',updatedAt:Date.now(),messages:[]};this.sessions.unshift(session);}
    session.messages=messages.map(message);
    if(!session.title||session.title==='新对话')session.title=derivedTitle(session.messages);
    session.updatedAt=Date.now();
    this.activeId=session.id;this.trim();
    try{this.save();}catch(error){if(previousSession)Object.assign(session,previousSession);this.sessions=previousSessions;this.activeId=previousActive;throw error;}
    return this.snapshot();
  }
  clear(){this.sessions=[];return this.create();}
  setPersistence(enabled){
    if(typeof enabled!=='boolean')throw new Error('会话保存开关无效');
    this.persistence=enabled;
    if(this.persistence)this.save();
    else{try{fs.rmSync(this.file,{force:true});}catch(error){this.log('会话文件清理失败：'+String(error.message||error));}}
    return this.snapshot();
  }
  trim(){if(this.sessions.length>this.maxSessions)this.sessions=this.sessions.slice(0,this.maxSessions);}
}
module.exports={Conversations,conversationMessage:message,MAX_CONVERSATION_PAYLOAD};
