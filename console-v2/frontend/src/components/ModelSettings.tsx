import {useEffect,useRef,useState} from 'react';
import {Eye,EyeOff,Trash2} from 'lucide-react';
import {host} from '../host';
import type {LocalService,ModelConfigSnapshot,ModelConnectionTest,ReasoningEffort} from '../host/types';
import cloudPresets from '../../electron/shared/cloud-presets.json';

const LOCAL_HOSTS=['127.0.0.1','localhost','[::1]'];
const LM_STUDIO='http://127.0.0.1:1234/v1';
const OLLAMA='http://127.0.0.1:11434/v1';
const openAiPreset=cloudPresets[0];
function connectionMode(value:string){
  try{return LOCAL_HOSTS.includes(new URL(value).hostname)?'local':'cloud';}
  catch{return 'local';}
}
// The address box can hold anything while it is being edited, so never parse it blind.
const hostOf=(value:string)=>{try{return new URL(value).host;}catch{return '尚未填写的地址';}};
type TestFeedback={kind:'success'|'manual'|'auth'|'network'|'address'|'response';title:string;detail:string};
type ConfirmAction={kind:'removeMainKey'}|{kind:'deleteProfile';id:string;name:string;endpoint:string;model:string;keyPresent:boolean}|{kind:'updateProfile';id:string;name:string;endpoint:string;model:string;keyPresent:boolean;diff:string}|{kind:'useProfile';id:string;name:string;endpoint:string;model:string};
function classifyTestError(value:unknown,secret:string,local:boolean):TestFeedback{
  const raw=errorText(value,secret),text=raw.replace(/^Error invoking remote method '[^']+':\s*(?:Error:\s*)?/,''),status=text.match(/\b(\d{3})\b/)?.[1];
  if(status==='401'||status==='403'||text.includes('服务拒绝访问'))return {kind:'auth',title:'服务拒绝访问',detail:local?'检查本地服务要求的 API 密钥。':'检查 API 密钥和模型访问权限。'};
  if(/HTTPS|地址无效|URL|凭据|协议/i.test(text))return {kind:'address',title:'服务地址需要调整',detail:local?'填写本机服务提供的 API 地址，例如 http://127.0.0.1:11434/v1。':'使用服务商提供的 HTTPS API 根地址。'};
  if(/无法连接|超时|网络|fetch failed|ENOTFOUND|ECONN|TLS/i.test(text))return {kind:'network',title:'暂时无法连接服务',detail:local?'确认本地模型服务已启动，再检查端口和 API 地址。':'检查网络、地址和服务状态后重试。'};
  if(status)return {kind:'response',title:`服务返回 ${status}`,detail:'服务已返回错误状态。检查 API 根地址、额度和服务商兼容说明。'};
  return {kind:'response',title:'无法读取模型列表',detail:'服务可能返回了不兼容的数据；可按服务商文档手动填写模型 ID。'};
}

export function ModelSettings({onSaved}:{onSaved?:()=>void}){
  const [config,setConfig]=useState<ModelConfigSnapshot|null>(null);
  const [mode,setMode]=useState<'local'|'cloud'>('local');
  const [endpoint,setEndpoint]=useState('http://127.0.0.1:1235/v1'),[model,setModel]=useState(''),[key,setKey]=useState('');
  const [reasoningEffort,setReasoningEffort]=useState<ReasoningEffort>('auto');
  const [modelOptions,setModelOptions]=useState<string[]>([]),[testResult,setTestResult]=useState<ModelConnectionTest|null>(null);
  const [testFeedback,setTestFeedback]=useState<TestFeedback|null>(null);
  const [showKey,setShowKey]=useState(false);
  const [services,setServices]=useState<LocalService[]|null>(null),[scanning,setScanning]=useState(false);
  const [profileId,setProfileId]=useState(''),[profileName,setProfileName]=useState(''),[includeProfileKey,setIncludeProfileKey]=useState(false);
  const [,setClearKey]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[error,setError]=useState('');
  const [confirmAction,setConfirmAction]=useState<ConfirmAction|null>(null);
  const confirmButtonRef=useRef<HTMLButtonElement>(null);
  const keyInputRef=useRef<HTMLInputElement>(null);
  const selectedProfile=config?.profiles?.find(profile=>profile.id===profileId);
  const local=mode==='local';
  const preset=local?undefined:cloudPresets.find(item=>item.endpoint===endpoint.trim().replace(/\/$/,''));
  const modelId=model.trim()||preset?.model||'';
  const savedKey=!!config?.keyPresent&&endpoint.trim().replace(/\/$/,'')===config.endpoint;
  const writesBlocked=!!(config?.secretUnavailable||config?.configUnavailable);
  function clearConnectionTest(){
    setTestResult(null);
    setTestFeedback(null);
    setModelOptions([]);
  }
  function editConnection(address:string,name=''){
    setEndpoint(address);
    setModel(name);
    setKey('');
    setShowKey(false);
    setError('');
    setMessage('');
    clearConnectionTest();
  }
  function switchMode(next:'local'|'cloud'){
    if(next===mode)return;
    setMode(next);
    if(config&&connectionMode(config.endpoint)===next){
      editConnection(config.endpoint,config.model);
      setReasoningEffort(config.reasoningEffort||'auto');
    }else{
      editConnection(next==='local'?'':openAiPreset.endpoint,next==='local'?'':openAiPreset.model);
      setReasoningEffort('auto');
    }
  }
  function choosePreset(item:(typeof cloudPresets)[number]){
    if(item!==preset){
      const alreadySaved=config?.endpoint===item.endpoint;
      editConnection(item.endpoint,alreadySaved&&config.model?config.model:item.model);
      setReasoningEffort(alreadySaved?config.reasoningEffort||'auto':'auto');
    }
    keyInputRef.current?.focus();
  }
  function validatePresetKey(){
    if(!preset||key.trim()||savedKey)return true;
    setError(`请输入 ${preset.label} 的 API 密钥。`);
    keyInputRef.current?.focus();
    return false;
  }
  function validateConnection(){
    try{
      const url=new URL(endpoint.trim());
      if(local&&LOCAL_HOSTS.includes(url.hostname)&&['http:','https:'].includes(url.protocol))return true;
      if(!local&&url.protocol==='https:'&&!LOCAL_HOSTS.includes(url.hostname))return true;
    }catch{/* The field may be empty or incomplete. */}
    setError(local?'请填写本机服务地址，例如 http://127.0.0.1:11434/v1。':'请填写云端服务的 HTTPS 地址。');
    setMessage('');
    clearConnectionTest();
    return false;
  }
  async function scan(){
    if(!host?.modelDiscover)return;
    setScanning(true);
    try{setServices(await host.modelDiscover());}
    catch(e){setError(errorText(e,key));}finally{setScanning(false);}
  }
  // Use the detected address directly; the form remains available for optional credentials.
  async function useService(item:LocalService){
    if(!host?.modelConfigSet)return;
    setBusy(true);setError('');setMessage('');
    try{
      const value=await host.modelConfigSet({endpoint:item.endpoint,model:config?.endpoint===item.endpoint?config.model:'',reasoningEffort});
      setConfig(value);
      editConnection(value.endpoint,value.model);
      setMode('local');
      setModelOptions(item.models);
      setMessage(`已选用 ${item.label}`);
      onSaved?.();
    }
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  useEffect(()=>{let live=true;host?.modelConfig?.().then(v=>{if(live){setConfig(v);setEndpoint(v.endpoint);setModel(v.model);setReasoningEffort(v.reasoningEffort||'auto');setMode(connectionMode(v.endpoint));}}).catch(e=>{if(live)setError(String(e.message||e));});void scan();return()=>{live=false;};},[]);
  async function save(){
    if(!host?.modelConfigSet||!validateConnection()||!validatePresetKey())return;
    setBusy(true);setError('');setMessage('');
    try{
      const value=await host.modelConfigSet({endpoint:endpoint.trim(),model:modelId,reasoningEffort,apiKey:key.trim()||undefined});
      setConfig(value);
      editConnection(value.endpoint,value.model);
      setMessage(local?'已保存，下次打开 Yuki 会自动使用':preset?`已保存 ${preset.label}，可返回对话`:'模型配置已保存');
      onSaved?.();
    }
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  async function testConnection(){
    if(!host?.modelTest||!validateConnection()||!validatePresetKey())return;
    setBusy(true);setError('');setMessage('');clearConnectionTest();
    try{const result=await host.modelTest({endpoint:endpoint.trim(),model:modelId,apiKey:key.trim()||undefined});setTestResult(result);setModelOptions(result.models);setTestFeedback({kind:result.listingAvailable&&result.models.length>0&&result.modelListed!==false?'success':'manual',title:result.listingAvailable?(result.modelListed===false?'连接成功，模型 ID 未匹配':result.models.length?'已连接服务':'服务已响应，未返回模型'):'服务不提供模型列表',detail:result.message});}
    catch(e){setTestFeedback(classifyTestError(e,key,local));}
    finally{setBusy(false);}
  }
  async function saveAttachments(enabled:boolean){
    if(!host?.modelAttachmentsSet)return;
    setBusy(true);setError('');setMessage('');
    try{setConfig(await host.modelAttachmentsSet(enabled));setMessage(enabled?'已允许把附件交给云端服务':'附件将只发给本机模型');}
    catch(e){setError(errorText(e,key));try{const fresh=await host.modelConfig?.();if(fresh)setConfig(fresh);}catch{/* 保持当前显示，错误已可见 */}}
    finally{setBusy(false);}
  }
  async function commitProfile(mode:'new'|'update'){
    if(!host?.modelProfileSave||!validateConnection())return;
    const name=profileName.trim();if(!name){setError('请先填写配置档案名称');return;}
    const current=selectedProfile;
    if(mode==='update'&&!current){setError('请先选择要更新的配置档案');return;}
    if(mode==='new'&&config?.profiles?.some(profile=>profile.name.toLocaleLowerCase()===name.toLocaleLowerCase())){setError('已存在同名配置档案，请选择该档案后更新，或修改名称。');return;}
    if(includeProfileKey&&!key&&!((config?.keyPresent&&endpoint.trim()===config.endpoint)||(mode==='update'&&current?.keyPresent&&current.endpoint===endpoint.trim()))){setError('此档案选择了保存密钥，但当前没有可复用的密钥。请先输入 API 密钥。');return;}
    setBusy(true);setError('');setMessage('');
    try{const value=await host.modelProfileSave({id:mode==='update'?profileId:undefined,name,endpoint:endpoint.trim(),model:modelId,reasoningEffort,includeApiKey:includeProfileKey,apiKey:includeProfileKey?(key||undefined):undefined});setConfig(value);const saved=value.profiles?.find(profile=>profile.id===(mode==='update'?profileId:undefined))||value.profiles?.find(profile=>profile.name===name);setProfileId(saved?.id||'');setProfileName(name);if(includeProfileKey)setKey('');setIncludeProfileKey(!!saved?.keyPresent);setClearKey(false);setMessage(mode==='update'?'配置档案已更新':'已保存为新配置档案');}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  function requestProfileSave(mode:'new'|'update'){
    const name=profileName.trim(),current=selectedProfile;
    if(!name){setError('请先填写配置档案名称');return;}
    if(mode==='update'&&!current){setError('请先选择要更新的配置档案');return;}
    if(mode==='new'&&config?.profiles?.some(profile=>profile.name.toLocaleLowerCase()===name.toLocaleLowerCase())){setError('已存在同名配置档案，请选择该档案后更新，或修改名称。');return;}
    if(mode==='update'&&current){
      const changes=[current.name!==name?`名称：${current.name} → ${name}`:'',current.endpoint!==endpoint.trim()?`服务地址：${current.endpoint} → ${endpoint.trim()}`:'',current.model!==modelId?`模型：${current.model||'未设置'} → ${modelId||'未设置'}`:'',current.keyPresent&&!includeProfileKey?'将从此档案移除加密密钥':'',!current.keyPresent&&includeProfileKey?'将为此档案加密保存密钥':''].filter(Boolean);
      setConfirmAction({kind:'updateProfile',id:current.id,name,endpoint:endpoint.trim(),model:modelId,keyPresent:current.keyPresent,diff:changes.length?changes.join('\n'):'档案内容没有变化'});return;
    }
    void commitProfile('new');
  }
  async function useProfile(confirmed=false){
    if(!host?.modelProfileUse||!profileId)return;
    const profile=selectedProfile;if(!profile)return;
    if(!confirmed&&!profile.keyPresent&&config?.keyPresent){setConfirmAction({kind:'useProfile',id:profile.id,name:profile.name,endpoint:profile.endpoint,model:profile.model});return;}
    setBusy(true);setError('');setMessage('');
    try{const previousEndpoint=config?.endpoint;const value=await host.modelProfileUse(profileId);const nextMode=connectionMode(value.endpoint);setConfig(value);editConnection(value.endpoint,value.model);setReasoningEffort(value.reasoningEffort||'auto');setMode(nextMode);setClearKey(false);const loaded=value.profiles?.find(item=>item.id===profileId);setProfileName(loaded?.name||'');setMessage(!loaded?.keyPresent&&nextMode==='cloud'?'配置档案已加载；档案未保存密钥，请重新输入 API 密钥。':previousEndpoint!==value.endpoint&&nextMode==='cloud'?'配置档案已加载；云端附件授权已关闭，请为新服务重新授权。':'配置档案已加载');onSaved?.();}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  async function deleteProfile(id=profileId){
    if(!host?.modelProfileDelete||!id)return;
    setBusy(true);setError('');setMessage('');
    try{const value=await host.modelProfileDelete(id);setConfig(value);setProfileId(current=>current===id?'':current);setProfileName('');setMessage('配置档案已删除');}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  async function removeMainKey(){
    if(!host?.modelConfigSet)return;
    setBusy(true);setError('');setMessage('');
    try{const value=await host.modelConfigSet({endpoint:config?.endpoint||endpoint.trim(),model:config?.model||model.trim(),reasoningEffort:config?.reasoningEffort||reasoningEffort,clearKey:true});setConfig(value);setKey('');setShowKey(false);setConfirmAction(null);setMessage('已移除主连接密钥。');}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  async function confirm(){
    const action=confirmAction;if(!action)return;
    if(action.kind==='removeMainKey'){await removeMainKey();return;}
    if(action.kind==='deleteProfile'){setConfirmAction(null);await deleteProfile(action.id);return;}
    if(action.kind==='updateProfile'){setConfirmAction(null);await commitProfile('update');}
    if(action.kind==='useProfile'){setConfirmAction(null);await useProfile(true);}
  }
  useEffect(()=>{if(!confirmAction)return;const previous=document.activeElement as HTMLElement|null;confirmButtonRef.current?.focus();const onKey=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();setConfirmAction(null);}};window.addEventListener('keydown',onKey);return()=>{window.removeEventListener('keydown',onKey);previous?.focus();};},[confirmAction]);
  const picks=(services||[]).filter(item=>item.running||(item.builtin&&config?.builtinEnabled));
  const connectionFields=<>
          <label>服务地址<input type="url" required disabled={busy} readOnly={!!preset} value={endpoint} onChange={e=>{setEndpoint(e.target.value);setKey('');setShowKey(false);setMessage('');setError('');clearConnectionTest();}} placeholder={local?OLLAMA:'https://api.example.com/v1'} maxLength={500}/></label>
          <label>模型名称<input list="model-config-options" disabled={busy} value={model} onChange={e=>{setModel(e.target.value);setTestResult(null);setTestFeedback(null);}} placeholder={preset?.model||(modelOptions.length?'选择或手动输入模型 ID':'手动输入，或测试后选择')} maxLength={300}/><datalist id="model-config-options">{[...new Set(modelOptions)].map(id=><option value={id} key={id}/>)}</datalist></label>
  </>;
  return <div className={'model-settings model-settings-page'+(local?'':' is-cloud')}><div className="model-settings-switch"><div><strong>连接方式</strong><small>选择雪要使用的模型来源</small></div><div className="segmented" role="group" aria-label="模型连接方式">{(['local','cloud'] as const).map(m=><button type="button" key={m} aria-pressed={mode===m} className={mode===m?'selected':''} disabled={busy} onClick={()=>switchMode(m)}>{m==='local'?'本地模型':'云端 API'}</button>)}</div></div>
    <form className="model-settings-form" onSubmit={e=>{e.preventDefault();void save();}}>
    <div className="model-settings-grid" data-verified={testResult?.keyVerified?'true':'false'}>
      <div className="model-settings-main">
        {local&&<section className="model-config-block model-local" aria-label="本机模型服务">
          <div className="model-local-heading"><div><strong>本机模型服务</strong><span>选用已运行的模型服务或内置 Qwen</span></div><button type="button" className="text-link" disabled={scanning||!host?.modelDiscover} onClick={()=>void scan()}>{scanning?'扫描中…':'重新扫描'}</button></div>
          {picks.length?<ul className="model-local-list">{picks.map(item=><li key={item.endpoint} className={item.endpoint===endpoint?'selected':''}>
            <div className="model-local-id"><strong>{item.label}</strong><small>{item.running?`${item.models.length} 个模型 · 端口 ${item.port}${item.models.length?` · ${item.models.slice(0,2).join('、')}${item.models.length>2?' 等':''}`:''}`:(item.note||'未启动')}</small></div>
            <button type="button" className="button secondary" disabled={busy||writesBlocked||item.endpoint===endpoint&&item.endpoint===config?.endpoint&&item.running} onClick={()=>void useService(item)}>{item.endpoint===endpoint&&item.endpoint===config?.endpoint&&item.running?'使用中':item.running?'选用':'启动并选用'}</button>
          </li>)}</ul>:<p className="muted">{!host?.modelDiscover?'请在桌面应用中扫描本机服务。':scanning?'正在扫描本机…':'未发现运行中的服务。启动服务后可重新扫描，或手动填写地址。'}</p>}
        </section>}
        <section className="model-config-block model-endpoint-block">
          <div className="model-config-heading"><div><strong>{local?'连接自己的本地模型':'选择云端服务'}</strong><span>{local?'先在本机启动模型服务，再填写它的 API 地址。':'选一个预设，填入对应服务的 API 密钥。'}</span></div></div>
          <div className="model-presets" role="group" aria-label={local?'本地服务地址预设':'云端服务预设'}>
            {local&&<span>常用地址</span>}
            {local?<><button type="button" disabled={busy} onClick={()=>editConnection(OLLAMA)}>Ollama</button><button type="button" disabled={busy} onClick={()=>editConnection(LM_STUDIO)}>LM Studio</button></>:cloudPresets.map(item=><button key={item.endpoint} type="button" aria-pressed={item===preset} disabled={busy} onClick={()=>choosePreset(item)}>{item.label}</button>)}
            <button type="button" disabled={busy} aria-pressed={local?undefined:!preset} onClick={()=>{editConnection('');setReasoningEffort('auto');}}>自定义</button>
          </div>
          {!preset&&connectionFields}
          <label>{local?'API 密钥（可选）':preset?`${preset.label} API 密钥`:'API 密钥'}<div className="model-secret-field"><input ref={keyInputRef} type={showKey?'text':'password'} autoComplete="new-password" disabled={busy} value={key} onChange={e=>{setKey(e.target.value);setError('');setMessage('');clearConnectionTest();}} placeholder={savedKey?'已安全保存；留空继续使用':local?'服务需要验证时填写':'粘贴服务商 API 密钥'} maxLength={4096}/><button type="button" className="icon-button model-secret-toggle" onClick={()=>setShowKey(value=>!value)} aria-label={showKey?'隐藏 API 密钥':'查看 API 密钥'} title={showKey?'隐藏密钥明文，继续以圆点显示。':'暂时显示已输入的 API 密钥，方便核对后再保存。'}><>{showKey?<EyeOff size={15}/>:<Eye size={15}/>}</></button></div>{savedKey&&!key&&<small className="model-field-help">密钥已保存在本机加密存储中；留空会继续使用它。</small>}{savedKey&&!!key&&<small className="model-field-help">保存后将替换此前保存在本机的密钥。</small>}</label>
          {preset&&<details className="model-preset-details" key={preset.endpoint}>
            <summary>连接设置 <small title={modelId}>{modelId}</small></summary>
            {connectionFields}
          </details>}
          {savedKey&&<button type="button" className="text-link model-secret-remove" disabled={busy||writesBlocked} onClick={()=>setConfirmAction({kind:'removeMainKey'})}>移除已保存的主连接密钥</button>}
          {!local&&config?.endpoint===endpoint&&<div className="model-remote-consent"><label className="inline-check"><input type="checkbox" checked={config?.endpoint===endpoint&&config.allowRemoteAttachments===true} disabled={busy||!host?.modelAttachmentsSet||writesBlocked} onChange={e=>void saveAttachments(e.target.checked)}/>允许附件发送到云端</label><p>{config?.allowRemoteAttachments?`已授权 ${hostOf(endpoint)}。发送前需确认图片和 OCR 文字。`:'默认关闭。开启后，每次发送前仍需确认附件内容。'}</p></div>}
          {config?.secretUnavailable&&<p role="alert" className="save-error">无法读取本机已有密钥，已暂停修改配置以免覆盖它。请检查系统密钥存储后重新打开 Yuki。</p>}
          {config?.configUnavailable&&<p role="alert" className="save-error">配置文件无法读取，已暂停修改以避免覆盖原有数据。请检查配置文件后重新打开 Yuki。</p>}
          <div className="model-config-actions"><button type="button" className="button secondary" disabled={busy||!host?.modelTest} onClick={()=>void testConnection()}>{busy?'正在连接…':modelOptions.length?'重新测试并刷新模型':'测试连接并读取模型'}</button><button type="submit" className="button primary" disabled={busy||!host?.modelConfigSet||writesBlocked}>{busy?'处理中…':local||preset?'保存并使用':'保存配置'}</button>{error&&<p role="alert" className="save-error">{error}</p>}{message&&<p role="status" className="model-save-message">{message}</p>}</div>
          {testFeedback&&<div className={`model-test-feedback ${testFeedback.kind}`} role={testFeedback.kind==='auth'||testFeedback.kind==='network'||testFeedback.kind==='address'||testFeedback.kind==='response'?'alert':'status'}><strong>{testFeedback.title}</strong><p>{testFeedback.detail}</p>{testResult?.modelListed===false&&!local&&<small>当前输入的模型 ID 不在服务列表中；如它是服务端别名，可核对文档后仍尝试保存。</small>}{!local&&testResult?.keyVerified===false&&testResult?.listingAvailable&&<small>本次连接未验证 API 密钥。</small>}</div>}
          {config&&!config.keyPersistent&&<p className="model-field-help">当前系统加密不可用，密钥仅在本次运行保留。</p>}
          <p className="model-field-help">{local?'轻量版也可连接兼容 OpenAI API 的本机服务。':preset?'聊天内容会发送到所选服务。':'仅支持兼容 OpenAI Chat Completions 的 HTTPS 接口。聊天内容会发送到所选服务。'}</p>
        </section>
      </div>
      <aside className="model-config-block model-profiles-block"><div className="model-config-heading"><div><strong>配置档案</strong><span>保存常用的服务地址和模型，可选加密保存密钥</span></div></div>
        {local&&config?.model&&connectionMode(config.endpoint)==='local'&&<p className="model-profile-summary">启动时使用 {config.model}</p>}
        <div className="model-profile-picker"><select aria-label="选择配置档案" value={profileId} disabled={busy||!config?.profiles?.length} onChange={e=>{const id=e.target.value;setProfileId(id);const profile=config?.profiles?.find(item=>item.id===id);setProfileName(profile?.name||'');setIncludeProfileKey(!!profile?.keyPresent);}}><option value="">选择已保存档案</option>{config?.profiles?.map(profile=><option value={profile.id} key={profile.id}>{profile.name}{profile.keyPresent?' · 含加密密钥':' · 未保存密钥'}</option>)}</select><button type="button" className="button secondary" disabled={busy||!profileId} onClick={()=>void useProfile()}>加载</button><button type="button" className="icon-button bordered" disabled={busy||!selectedProfile} onClick={()=>selectedProfile&&setConfirmAction({kind:'deleteProfile',id:selectedProfile.id,name:selectedProfile.name,endpoint:selectedProfile.endpoint,model:selectedProfile.model,keyPresent:selectedProfile.keyPresent})} aria-label="删除配置档案" title="移除此配置档案及其保存的连接信息；操作前会再次确认。"><Trash2 size={15}/></button></div>
        {selectedProfile&&<p className="model-profile-summary">{selectedProfile.endpoint} · {selectedProfile.model||'未设置模型'} · {selectedProfile.keyPresent?'此档案含本机加密密钥':'此档案不含密钥'}</p>}
        <div className="model-profile-save"><input aria-label="配置档案名称" value={profileName} onChange={e=>setProfileName(e.target.value)} placeholder="输入配置档案名称" maxLength={80}/><label className="inline-check"><input type="checkbox" checked={includeProfileKey} onChange={e=>setIncludeProfileKey(e.target.checked)}/>同时加密保存 API 密钥</label><small className="model-field-help">不勾选时，档案不保存密钥；加载后需要重新输入。此档案密钥独立于主连接密钥。</small><div className="model-profile-actions"><button type="button" className="button secondary" disabled={busy||!profileName.trim()||writesBlocked} onClick={()=>requestProfileSave('new')}>保存为新档案</button><button type="button" className="button secondary" disabled={busy||!selectedProfile||writesBlocked} onClick={()=>requestProfileSave('update')}>更新所选档案</button></div></div>
      </aside>
    </div>
    </form>
    {confirmAction&&<div className="model-confirm-scrim" onMouseDown={event=>{if(event.target===event.currentTarget)setConfirmAction(null);}}><section className="model-confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="model-confirm-title"><strong id="model-confirm-title">{confirmAction.kind==='removeMainKey'?'移除主连接密钥？':confirmAction.kind==='deleteProfile'?'删除配置档案？':confirmAction.kind==='useProfile'?'加载不含密钥的档案？':'确认更新配置档案'}</strong>{confirmAction.kind==='removeMainKey'?<p>将从本机加密配置中移除当前主连接密钥。服务要求验证时需要重新输入密钥；已保存到配置档案中的密钥不受影响。</p>:confirmAction.kind==='deleteProfile'?<><p>档案：{confirmAction.name}<br/>服务：{confirmAction.endpoint}<br/>模型：{confirmAction.model||'未设置'}<br/>密钥：{confirmAction.keyPresent?'档案密钥也会一并移除，不影响主连接密钥':'不含密钥'}</p><p>删除后不能从 Yuki 恢复；当前已加载的连接不会改变。</p></>:confirmAction.kind==='useProfile'?<p>档案：{confirmAction.name}<br/>服务：{confirmAction.endpoint}<br/>模型：{confirmAction.model||'未设置'}<br/>档案不含密钥。加载会移除当前主连接中已保存的密钥，之后需要重新输入。</p>:<><p>档案：{confirmAction.name}<br/>服务：{confirmAction.endpoint}<br/>模型：{confirmAction.model||'未设置'}<br/>密钥：{includeProfileKey?'更新后包含本机加密密钥':'更新后不包含密钥'}</p><pre>{confirmAction.diff}</pre></>}<div className="model-confirm-actions"><button type="button" className="button secondary" disabled={busy} onClick={()=>setConfirmAction(null)}>取消</button><button ref={confirmButtonRef} type="button" className="button primary" disabled={busy} onClick={()=>void confirm()}>{busy?'处理中…':confirmAction.kind==='removeMainKey'?'移除密钥':confirmAction.kind==='deleteProfile'?'确认删除':confirmAction.kind==='useProfile'?'加载档案':'确认更新'}</button></div></section></div>}
  </div>;
}

function errorText(value:unknown,secret:string){const raw=value instanceof Error?value.message:String(value);return secret?raw.split(secret).join('••••'):raw;}
