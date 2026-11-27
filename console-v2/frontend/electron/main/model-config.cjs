'use strict';
const fs=require('node:fs/promises');
const path=require('node:path');
const {randomUUID}=require('node:crypto');
const {modelListHeaders}=require('./cloud-providers.cjs');

const REASONING_EFFORTS=new Set(['auto','low','medium','high']);
function reasoningEffort(value){return REASONING_EFFORTS.has(value)?value:'auto';}
function endpoint(value){
  if(typeof value!=='string'||value.length>500)throw new Error('服务地址无效');
  const u=new URL(value);
  if(u.username||u.password||u.search||u.hash||!['http:','https:'].includes(u.protocol))throw new Error('地址不能包含凭据、查询或片段');
  if(u.protocol==='http:'&&!['localhost','127.0.0.1','[::1]'].includes(u.hostname))throw new Error('远程模型请使用 HTTPS');
  return u.href.replace(/\/$/,'');
}
function checkedModel(value,label='模型名称'){
  const model=value||'';
  if(typeof model!=='string'||model.length>300)throw new Error(`${label}无效`);
  return model.trim();
}
function checkedKey(value){
  if(value!==undefined&&(typeof value!=='string'||value.length>4096||/[\r\n]/.test(value)))throw new Error('API 密钥无效');
  return value?.trim()||'';
}

class ModelConfig {
  constructor(file,safeStorage){
    this.file=file;this.storage=safeStorage;
    this.value={endpoint:'http://127.0.0.1:1235/v1',model:'',reasoningEffort:'auto'};
    this.connectionConfigured=false;
    this.translation={mode:'system',provider:'local',endpoint:'http://127.0.0.1:1235/v1',model:'',reasoningEffort:'auto',key:''};
    this.builtinEnabled=false;this.allowRemoteAttachments=false;this.key='';this.profiles=[];this.encryptionAvailable=false;this.secretUnavailable=false;this.configUnavailable=false;
    this.ready=this.load();
  }
  async load(){
    this.encryptionAvailable=await this.storage.isAsyncEncryptionAvailable().catch(()=>false);
    let raw,saved;
    try{raw=await fs.readFile(this.file,'utf8');}catch(error){if(error.code==='ENOENT')return this;this.configUnavailable=true;return this;}
    try{saved=JSON.parse(raw);}catch{this.configUnavailable=true;return this;}
    this.builtinEnabled=saved.builtinEnabled===true;
    this.allowRemoteAttachments=saved.allowRemoteAttachments===true;
    try{this.value={endpoint:endpoint(saved.endpoint),model:checkedModel(saved.model),reasoningEffort:reasoningEffort(saved.reasoningEffort)};}catch{}
    const decrypt=async secret=>{
      if(!secret)return '';
      if(!this.encryptionAvailable){this.secretUnavailable=true;return '';}
      try{let value=await this.storage.decryptStringAsync(Buffer.from(secret,'base64'));if(value.shouldReEncrypt)value=await this.storage.decryptStringAsync(Buffer.from(secret,'base64'));return value.result;}catch{this.secretUnavailable=true;return '';}
    };
    this.key=await decrypt(saved.secret);
    // Older files did not distinguish the default address from an explicitly saved connection.
    this.connectionConfigured=typeof saved.connectionConfigured==='boolean'
      ?saved.connectionConfigured
      :!/^(http:\/\/127\.0\.0\.1:123[45]\/v1)$/.test(this.value.endpoint)||!!(this.value.model||saved.secret);
    const t=saved.translation&&typeof saved.translation==='object'?saved.translation:{};
    try{
      const translationEndpoint=endpoint(t.endpoint||this.translation.endpoint);
      this.translation={mode:t.mode==='custom'?'custom':'system',provider:t.provider==='cloud'||(!t.provider&&translationEndpoint.startsWith('https:'))?'cloud':'local',endpoint:translationEndpoint,model:checkedModel(t.model,'翻译模型'),reasoningEffort:reasoningEffort(t.reasoningEffort),key:await decrypt(t.secret)};
    }catch{}
    const profiles=Array.isArray(saved.profiles)?saved.profiles:[];
    this.profiles=(await Promise.all(profiles.map(async profile=>{
      if(!profile||typeof profile!=='object')return null;
      const name=String(profile.name||'').trim(),id=String(profile.id||'').trim();if(!id||!name)return null;
      try{return {id,name:name.slice(0,80),endpoint:endpoint(profile.endpoint),model:checkedModel(profile.model,'档案模型'),reasoningEffort:reasoningEffort(profile.reasoningEffort),key:await decrypt(profile.secret)};}catch{return null;}
    }))).filter(Boolean);
    return this;
  }
  async secret(value){return value&&this.encryptionAvailable?(await this.storage.encryptStringAsync(value)).toString('base64'):undefined;}
  async serialize(){
    const secret=await this.secret(this.key);
    const translation={mode:this.translation.mode,provider:this.translation.provider,endpoint:this.translation.endpoint,model:this.translation.model,reasoningEffort:this.translation.reasoningEffort,secret:await this.secret(this.translation.key)};
    const profiles=await Promise.all(this.profiles.map(async profile=>({id:profile.id,name:profile.name,endpoint:profile.endpoint,model:profile.model,reasoningEffort:profile.reasoningEffort,secret:await this.secret(profile.key)})));
    return {...this.value,connectionConfigured:this.connectionConfigured,secret,builtinEnabled:this.builtinEnabled,allowRemoteAttachments:this.allowRemoteAttachments,translation,profiles};
  }
  async persist(){
    await this.ready;
    if(this.configUnavailable)throw new Error('模型配置文件无法读取，已暂停写入以免覆盖原文件。请检查本机配置文件后重新打开 Yuki。');
    if(this.secretUnavailable)throw new Error('系统暂时无法读取此前保存的密钥，已暂停写入以免覆盖密钥。请检查系统密钥存储后重新打开 Yuki。');
    const data=JSON.stringify(await this.serialize());
    await fs.mkdir(path.dirname(this.file),{recursive:true});
    const temp=`${this.file}.${process.pid}.${randomUUID()}.tmp`;
    try{await fs.writeFile(temp,data,{encoding:'utf8',mode:0o600});await fs.rename(temp,this.file);}catch(error){await fs.rm(temp,{force:true}).catch(()=>{});throw error;}
  }
  snapshot(){return {...this.value,builtinEnabled:this.builtinEnabled,allowRemoteAttachments:this.allowRemoteAttachments,keyPresent:!!this.key,keyPersistent:this.encryptionAvailable,secretUnavailable:this.secretUnavailable,configUnavailable:this.configUnavailable,translation:{mode:this.translation.mode,provider:this.translation.provider,endpoint:this.translation.endpoint,model:this.translation.model,reasoningEffort:this.translation.reasoningEffort,keyPresent:!!this.translation.key},profiles:this.profiles.map(({id,name,endpoint,model,reasoningEffort,key})=>({id,name,endpoint,model,reasoningEffort,keyPresent:!!key}))};}
  async setTranslation(input){
    await this.ready;
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['mode','provider','endpoint','model','reasoningEffort','apiKey','clearKey'].includes(k)))throw new Error('翻译模型配置无效');
    if(input.mode!=='system'&&input.mode!=='custom')throw new Error('翻译模型来源无效');
    if(input.provider!==undefined&&input.provider!=='local'&&input.provider!=='cloud')throw new Error('翻译模型类型无效');
    const value={mode:input.mode,provider:input.provider==='cloud'?'cloud':'local',endpoint:endpoint(input.endpoint),model:checkedModel(input.model,'翻译模型'),reasoningEffort:reasoningEffort(input.reasoningEffort)};
    if(input.clearKey!==undefined&&typeof input.clearKey!=='boolean')throw new Error('翻译模型密钥参数无效');
    let key=value.endpoint===this.translation.endpoint?this.translation.key:'';if(input.clearKey)key='';key=checkedKey(input.apiKey)||key;if(key&&!this.encryptionAvailable)throw new Error('系统加密不可用，API 密钥不会保存；请先启用系统密钥存储。');
    const previous=this.translation;this.translation={...value,key};try{await this.persist();}catch(error){this.translation=previous;throw error;}return this.snapshot();
  }
  async setBuiltinEnabled(enabled){await this.ready;if(typeof enabled!=='boolean')throw Error('内置模型开关无效');const previous=this.builtinEnabled;this.builtinEnabled=enabled;try{await this.persist();}catch(error){this.builtinEnabled=previous;throw error;}return this.snapshot();}
  async setRemoteAttachments(enabled){await this.ready;if(typeof enabled!=='boolean')throw Error('附件授权开关无效');const previous=this.allowRemoteAttachments;this.allowRemoteAttachments=enabled;try{await this.persist();}catch(error){this.allowRemoteAttachments=previous;throw error;}return this.snapshot();}
  async set(input){
    await this.ready;
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['endpoint','model','apiKey','clearKey','reasoningEffort'].includes(k)))throw new Error('模型配置无效');
    const value={endpoint:endpoint(input.endpoint),model:checkedModel(input.model),reasoningEffort:reasoningEffort(input.reasoningEffort)};
    if(input.clearKey!==undefined&&typeof input.clearKey!=='boolean')throw new Error('密钥清除参数无效');
    let key=value.endpoint===this.value.endpoint?this.key:'';if(input.clearKey)key='';key=checkedKey(input.apiKey)||key;if(key&&!this.encryptionAvailable)throw new Error('系统加密不可用，API 密钥不会保存；请先启用系统密钥存储。');
    return this.saveConnection(value,key);
  }
  async test(input,fetchImpl=fetch){
    await this.ready;
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['endpoint','model','apiKey'].includes(k)))throw new Error('连接测试参数无效');
    const target=endpoint(input.endpoint),model=checkedModel(input.model),supplied=checkedKey(input.apiKey);
    const key=supplied||(target===this.value.endpoint?this.key:'');
    const response=await fetchImpl(target+'/models',{headers:modelListHeaders(target,key),signal:AbortSignal.timeout(12000),redirect:'error'}).catch(()=>{throw new Error('无法连接服务，请检查地址、网络和服务状态');});
    if(!response.ok){
      if([404,405].includes(response.status))return {endpoint:target,models:model?[model]:[],listingAvailable:false,keyVerified:false,modelListed:null,message:'服务未提供模型列表，密钥尚未验证；请按服务文档填写模型 ID 后保存。'};
      if(response.status===401||response.status===403)throw new Error('服务拒绝访问，请检查 API 密钥和账号权限');
      throw new Error(`模型服务返回 ${response.status}，请检查服务地址`);
    }
    const payload=await response.json().catch(()=>null);
    if(!payload||!Array.isArray(payload.data))throw new Error('服务已响应，但没有返回可识别的模型列表');
    const models=[...new Set(payload.data.map(item=>item?.id).filter(id=>typeof id==='string'&&id.length>0&&id.length<=300&&!/embed/i.test(id)))];
    const modelListed=model?models.includes(model):null;
    const local=['127.0.0.1','localhost','[::1]'].includes(new URL(target).hostname);
    const localCount=models.length;
    if(model&&!modelListed)models.unshift(model);
    if(local&&!key){
      const message=modelListed===false?'连接成功，但填写的模型 ID 不在列表中。请核对后再保存。'
        :localCount?`已读取 ${localCount} 个模型。`:'未读取到模型，请先在本地服务中加载模型。';
      return {endpoint:target,models,listingAvailable:true,keyVerified:false,modelListed,message};
    }
    return {endpoint:target,models,listingAvailable:true,keyVerified:!!key,modelListed,message:!models.length?`服务已响应，但没有返回可用模型。${key?'API 密钥已被服务接受。':'本次未使用 API 密钥，尚未验证密钥。'}请按服务商文档填写模型 ID。`:modelListed===false?'连接成功，但填写的模型 ID 不在列表中；它可能是服务端别名，请核对权限后再保存。':!key?'服务已响应并读取模型；本次没有使用 API 密钥，因此尚未验证密钥。':`连接成功，读取到 ${models.length-(modelListed===false?1:0)} 个模型，API 密钥已被服务接受。`};
  }
  async saveProfile(input){
    await this.ready;
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['id','name','endpoint','model','apiKey','clearKey','includeApiKey','reasoningEffort'].includes(k)))throw new Error('配置档案无效');
    const name=typeof input.name==='string'?input.name.trim():'';if(!name||name.length>80||/[\r\n]/.test(name))throw new Error('档案名称无效');
    const value={endpoint:endpoint(input.endpoint),model:checkedModel(input.model,'档案模型'),reasoningEffort:reasoningEffort(input.reasoningEffort)};
    if(input.includeApiKey!==undefined&&typeof input.includeApiKey!=='boolean')throw new Error('密钥保存选项无效');
    if(input.clearKey!==undefined&&typeof input.clearKey!=='boolean')throw new Error('密钥清除参数无效');
    const id=input.id===undefined?'':String(input.id),index=id?this.profiles.findIndex(profile=>profile.id===id):-1;
    if(id&&index<0)throw new Error('配置档案不存在');if(index<0&&this.profiles.some(profile=>profile.name.toLocaleLowerCase()===name.toLocaleLowerCase()))throw new Error('已有同名配置档案');
    let key='';if(input.includeApiKey===true){const existing=index>=0?this.profiles[index]:null;key=checkedKey(input.apiKey)||(existing&&existing.endpoint===value.endpoint&&!input.clearKey?existing.key:'')||(value.endpoint===this.value.endpoint?this.key:'');if(input.clearKey)key='';if(key&&!this.encryptionAvailable)throw new Error('系统加密不可用，API 密钥不会保存；请先启用系统密钥存储。');}
    const previous=this.profiles,profile={id:index>=0?previous[index].id:randomUUID(),name,endpoint:value.endpoint,model:value.model,reasoningEffort:value.reasoningEffort,key};
    this.profiles=[...previous];if(index>=0)this.profiles[index]=profile;else this.profiles.push(profile);
    try{await this.persist();}catch(error){this.profiles=previous;throw error;}return this.snapshot();
  }
  async saveConnection(value,key){
    const previous={value:this.value,key:this.key,allowRemoteAttachments:this.allowRemoteAttachments,connectionConfigured:this.connectionConfigured};
    this.value=value;
    this.key=key;
    this.connectionConfigured=true;
    if(value.endpoint!==previous.value.endpoint)this.allowRemoteAttachments=false;
    try{await this.persist();}catch(error){Object.assign(this,previous);throw error;}
    return this.snapshot();
  }
  async useProfile(id){
    await this.ready;
    const profile=this.profiles.find(value=>value.id===id);
    if(!profile)throw new Error('配置档案不存在');
    const {endpoint,model,reasoningEffort,key}=profile;
    return this.saveConnection({endpoint,model,reasoningEffort},key);
  }
  async deleteProfile(id){await this.ready;const next=this.profiles.filter(profile=>profile.id!==id);if(next.length===this.profiles.length)throw new Error('配置档案不存在');const previous=this.profiles;this.profiles=next;try{await this.persist();}catch(error){this.profiles=previous;throw error;}return this.snapshot();}
}
module.exports={ModelConfig,endpoint,reasoningEffort};
