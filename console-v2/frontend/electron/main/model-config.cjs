'use strict';
const fs=require('node:fs');
function endpoint(value){
  if(typeof value!=='string'||value.length>500)throw new Error('服务地址无效');
  const u=new URL(value);
  if(u.username||u.password||u.search||u.hash||!['http:','https:'].includes(u.protocol))throw new Error('地址不能包含凭据、查询或片段');
  if(u.protocol==='http:'&&!['localhost','127.0.0.1','[::1]'].includes(u.hostname))throw new Error('远程模型请使用 HTTPS');
  return u.href.replace(/\/$/,'');
}
class ModelConfig {
  constructor(file,safeStorage){this.file=file;this.storage=safeStorage;this.value={endpoint:'http://127.0.0.1:1235/v1',model:''};this.builtinEnabled=false;this.key='';try{const saved=JSON.parse(fs.readFileSync(file,'utf8'));this.builtinEnabled=saved.builtinEnabled===true;this.value={endpoint:endpoint(saved.endpoint),model:String(saved.model||'').slice(0,300)};if(saved.secret&&safeStorage.isEncryptionAvailable())this.key=safeStorage.decryptString(Buffer.from(saved.secret,'base64'));}catch{}}
  snapshot(){return {...this.value,builtinEnabled:this.builtinEnabled,keyPresent:!!this.key,keyPersistent:this.storage.isEncryptionAvailable()};}
  setBuiltinEnabled(enabled){
    if(typeof enabled!=='boolean')throw Error('内置模型开关无效');
    const secret=this.key&&this.storage.isEncryptionAvailable()?this.storage.encryptString(this.key).toString('base64'):undefined;
    fs.writeFileSync(this.file,JSON.stringify({...this.value,secret,builtinEnabled:enabled}));
    this.builtinEnabled=enabled;return this.snapshot();
  }
  set(input){
    if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!['endpoint','model','apiKey','clearKey'].includes(k)))throw new Error('模型配置无效');
    const value={endpoint:endpoint(input.endpoint),model:input.model||''};
    if(typeof value.model!=='string'||value.model.length>300||(input.apiKey!==undefined&&(typeof input.apiKey!=='string'||input.apiKey.length>4096||/[\r\n]/.test(input.apiKey)))||(input.clearKey!==undefined&&typeof input.clearKey!=='boolean'))throw new Error('模型名称或密钥无效');
    // Never carry credentials to a different destination by accident.
    let key=value.endpoint===this.value.endpoint?this.key:'';
    if(input.clearKey)key='';if(input.apiKey)key=input.apiKey.trim();
    const secret=key&&this.storage.isEncryptionAvailable()?this.storage.encryptString(key).toString('base64'):undefined;
    fs.writeFileSync(this.file,JSON.stringify({...value,secret,builtinEnabled:this.builtinEnabled}));this.value=value;this.key=key;return this.snapshot();
  }
}
module.exports={ModelConfig,endpoint};
