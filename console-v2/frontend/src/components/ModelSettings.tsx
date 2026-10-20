import {useEffect,useState} from 'react';
import {host} from '../host';
import type {ModelConfigSnapshot} from '../host/types';

export function ModelSettings({onSaved}:{onSaved?:()=>void}){
  const [config,setConfig]=useState<ModelConfigSnapshot|null>(null);
  const [endpoint,setEndpoint]=useState('http://127.0.0.1:1235/v1'),[model,setModel]=useState(''),[key,setKey]=useState('');
  const [clearKey,setClearKey]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  useEffect(()=>{let live=true;host?.modelConfig?.().then(v=>{if(live){setConfig(v);setEndpoint(v.endpoint);setModel(v.model);}}).catch(e=>{if(live)setError(String(e.message||e));});return()=>{live=false;};},[]);
  async function save(){
    if(!host?.modelConfigSet)return;
    setBusy(true);setError('');setMessage('');
    try{const value=await host.modelConfigSet({endpoint:endpoint.trim(),model:model.trim(),apiKey:key||undefined,clearKey});setConfig(value);setKey('');setClearKey(false);setMessage('模型配置已保存');onSaved?.();}
    catch(e){setError(String(e instanceof Error?e.message:e));}finally{setBusy(false);}
  }
  return <details className="model-settings"><summary>模型服务设置</summary><form onSubmit={e=>{e.preventDefault();void save();}}>
    <label>服务地址<input type="url" required value={endpoint} onChange={e=>setEndpoint(e.target.value)} placeholder="https://api.example.com/v1" maxLength={500}/></label>
    <label>模型名称<input value={model} onChange={e=>setModel(e.target.value)} placeholder="留空后从模型列表选择" maxLength={300}/></label>
    <label>API 密钥<input type="password" autoComplete="off" value={key} onChange={e=>setKey(e.target.value)} placeholder={config?.keyPresent?'已配置；留空保留':'本地无认证服务可留空'} maxLength={4096}/></label>
    {config?.keyPresent&&<label className="inline-check"><input type="checkbox" checked={clearKey} onChange={e=>setClearKey(e.target.checked)}/>移除已保存的密钥</label>}
    <p className="note">兼容 OpenAI Chat Completions。支持 LM Studio、Ollama 的 /v1 接口及 HTTPS 云服务。云端聊天会发送你输入的对话内容。</p>
    {config&&!config.keyPersistent&&<p className="note">当前系统加密不可用，密钥仅在本次运行保留。</p>}
    {error&&<p role="alert" className="save-error">{error}</p>}{message&&<p role="status" className="note">{message}</p>}
    <button className="button primary" disabled={busy||!host?.modelConfigSet}>{busy?'保存中…':'保存配置'}</button>
  </form></details>;
}
