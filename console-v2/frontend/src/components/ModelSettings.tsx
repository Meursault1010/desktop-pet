import {useEffect,useRef,useState} from 'react';
import {Eye,EyeOff,Trash2} from 'lucide-react';
import {host} from '../host';
import type {LocalService,ModelConfigSnapshot,ModelConnectionTest,ReasoningEffort} from '../host/types';

const LOOPBACK=/^http:\/\/(127\.0\.0\.1|localhost|\[::1\])(:\d{2,5})?\//;
// The address box can hold anything while it is being edited, so never parse it blind.
const hostOf=(value:string)=>{try{return new URL(value).host;}catch{return '尚未填写的地址';}};
type TestFeedback={kind:'success'|'manual'|'auth'|'network'|'address'|'response';title:string;detail:string};
type ConfirmAction={kind:'removeMainKey'}|{kind:'deleteProfile';id:string;name:string;endpoint:string;model:string;keyPresent:boolean}|{kind:'updateProfile';id:string;name:string;endpoint:string;model:string;keyPresent:boolean;diff:string}|{kind:'useProfile';id:string;name:string;endpoint:string;model:string};
function classifyTestError(value:unknown,secret:string):TestFeedback{
  const raw=errorText(value,secret),text=raw.replace(/^Error invoking remote method '[^']+':\s*(?:Error:\s*)?/,''),status=text.match(/\b(\d{3})\b/)?.[1];
  if(status==='401'||status==='403')return {kind:'auth',title:'服务拒绝访问',detail:'检查 API 密钥、账号权限和该模型的访问权限。'};
  if(/HTTPS|地址无效|URL|凭据|协议/i.test(text))return {kind:'address',title:'服务地址需要调整',detail:'使用服务商提供的 HTTPS API 根地址，例如以 /v1 结尾的地址。'};
  if(/无法连接|超时|网络|fetch failed|ENOTFOUND|ECONN|TLS/i.test(text))return {kind:'network',title:'暂时无法连接服务',detail:'检查网络、地址和服务状态后重试。'};
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
  const selectedProfile=config?.profiles?.find(profile=>profile.id===profileId);
  const local=LOOPBACK.test(endpoint);
  const writesBlocked=!!(config?.secretUnavailable||config?.configUnavailable);
  async function scan(){
    if(!host?.modelDiscover)return;
    setScanning(true);
    try{setServices(await host.modelDiscover());}
    catch(e){setError(errorText(e,key));}finally{setScanning(false);}
  }
  // A running local server is picked, not configured: no address, no key.
  async function useService(item:LocalService){
    if(!host?.modelConfigSet)return;
    setBusy(true);setError('');setMessage('');
    try{const value=await host.modelConfigSet({endpoint:item.endpoint,model:'',reasoningEffort});setConfig(value);setEndpoint(value.endpoint);setModel('');setKey('');setShowKey(false);setClearKey(false);setMode('local');setMessage(`已选用 ${item.label}，正在读取模型列表…`);onSaved?.();}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  useEffect(()=>{let live=true;host?.modelConfig?.().then(v=>{if(live){setConfig(v);setEndpoint(v.endpoint);setModel(v.model);setReasoningEffort(v.reasoningEffort||'auto');setMode(v.endpoint.startsWith('https:')?'cloud':'local');}}).catch(e=>{if(live)setError(String(e.message||e));});void scan();return()=>{live=false;};},[]);
  async function save(){
    if(!host?.modelConfigSet)return;
    setBusy(true);setError('');setMessage('');
    try{const replacing=!!(key&&config?.keyPresent&&endpoint.trim()===config.endpoint);const value=await host.modelConfigSet({endpoint:endpoint.trim(),model:model.trim(),reasoningEffort,apiKey:key||undefined});setConfig(value);setKey('');setShowKey(false);setClearKey(false);setTestResult(null);setTestFeedback(null);setModelOptions([]);setMessage(replacing?'新密钥已加密保存，并替换原有密钥':'模型配置已保存');onSaved?.();}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  async function testConnection(){
    if(!host?.modelTest)return;
    setBusy(true);setError('');setMessage('');setTestResult(null);setModelOptions([]);
    try{const result=await host.modelTest({endpoint:endpoint.trim(),model:model.trim(),apiKey:key.trim()||undefined});setTestResult(result);setModelOptions(result.models);setTestFeedback({kind:result.listingAvailable&&result.models.length>0&&result.modelListed!==false?'success':'manual',title:result.listingAvailable?(result.modelListed===false?'连接成功，模型 ID 未匹配':result.models.length?'已连接服务':'服务已响应，未返回模型'):'服务不提供模型列表',detail:result.message});}
    catch(e){setTestFeedback(classifyTestError(e,key));}
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
    if(!host?.modelProfileSave)return;
    const name=profileName.trim();if(!name){setError('请先填写配置档案名称');return;}
    const current=selectedProfile;
    if(mode==='update'&&!current){setError('请先选择要更新的配置档案');return;}
    if(mode==='new'&&config?.profiles?.some(profile=>profile.name.toLocaleLowerCase()===name.toLocaleLowerCase())){setError('已存在同名配置档案，请选择该档案后更新，或修改名称。');return;}
    if(includeProfileKey&&!key&&!((config?.keyPresent&&endpoint.trim()===config.endpoint)||(mode==='update'&&current?.keyPresent&&current.endpoint===endpoint.trim()))){setError('此档案选择了保存密钥，但当前没有可复用的密钥。请先输入云端 API 密钥。');return;}
    setBusy(true);setError('');setMessage('');
    try{const value=await host.modelProfileSave({id:mode==='update'?profileId:undefined,name,endpoint:endpoint.trim(),model:model.trim(),reasoningEffort,includeApiKey:includeProfileKey,apiKey:includeProfileKey?(key||undefined):undefined});setConfig(value);const saved=value.profiles?.find(profile=>profile.id===(mode==='update'?profileId:undefined))||value.profiles?.find(profile=>profile.name===name);setProfileId(saved?.id||'');setProfileName(name);if(includeProfileKey)setKey('');setIncludeProfileKey(!!saved?.keyPresent);setClearKey(false);setMessage(mode==='update'?'配置档案已更新':'已保存为新配置档案');}
    catch(e){setError(errorText(e,key));}finally{setBusy(false);}
  }
  function requestProfileSave(mode:'new'|'update'){
    const name=profileName.trim(),current=selectedProfile;
    if(!name){setError('请先填写配置档案名称');return;}
    if(mode==='update'&&!current){setError('请先选择要更新的配置档案');return;}
    if(mode==='new'&&config?.profiles?.some(profile=>profile.name.toLocaleLowerCase()===name.toLocaleLowerCase())){setError('已存在同名配置档案，请选择该档案后更新，或修改名称。');return;}
    if(mode==='update'&&current){
      const changes=[current.name!==name?`名称：${current.name} → ${name}`:'',current.endpoint!==endpoint.trim()?`服务地址：${current.endpoint} → ${endpoint.trim()}`:'',current.model!==model.trim()?`模型：${current.model||'未设置'} → ${model.trim()||'未设置'}`:'',current.keyPresent&&!includeProfileKey?'将从此档案移除加密密钥':'',!current.keyPresent&&includeProfileKey?'将为此档案加密保存密钥':''].filter(Boolean);
      setConfirmAction({kind:'updateProfile',id:current.id,name,endpoint:endpoint.trim(),model:model.trim(),keyPresent:current.keyPresent,diff:changes.length?changes.join('\n'):'档案内容没有变化'});return;
    }
    void commitProfile('new');
  }
  async function useProfile(confirmed=false){
    if(!host?.modelProfileUse||!profileId)return;
    const profile=selectedProfile;if(!profile)return;
    if(!confirmed&&!profile.keyPresent&&config?.keyPresent){setConfirmAction({kind:'useProfile',id:profile.id,name:profile.name,endpoint:profile.endpoint,model:profile.model});return;}
    setBusy(true);setError('');setMessage('');
    try{const previousEndpoint=config?.endpoint;const value=await host.modelProfileUse(profileId);setConfig(value);setEndpoint(value.endpoint);setModel(value.model);setReasoningEffort(value.reasoningEffort||'auto');setMode(value.endpoint.startsWith('https:')?'cloud':'local');setKey('');setShowKey(false);setClearKey(false);const loaded=value.profiles?.find(item=>item.id===profileId);setProfileName(loaded?.name||'');setMessage(!loaded?.keyPresent&&value.endpoint.startsWith('https:')?'配置档案已加载；档案未保存密钥，请重新输入 API 密钥。':previousEndpoint!==value.endpoint&&value.endpoint.startsWith('https:')?'配置档案已加载；云端附件授权已关闭，请为新服务重新授权。':'配置档案已加载');onSaved?.();}
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
    try{const value=await host.modelConfigSet({endpoint:config?.endpoint||endpoint.trim(),model:config?.model||model.trim(),reasoningEffort:config?.reasoningEffort||reasoningEffort,clearKey:true});setConfig(value);setKey('');setShowKey(false);setConfirmAction(null);setMessage('已从本机移除主连接密钥；云端服务需要重新填写密钥后才能认证。');}
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
  return <div className="model-settings model-settings-page"><div className="model-settings-switch"><div><strong>连接方式</strong><small>选择雪要使用的模型来源</small></div><div className="segmented" role="group" aria-label="模型连接方式">{(['local','cloud'] as const).map(m=><button type="button" key={m} aria-pressed={mode===m} className={mode===m?'selected':''} onClick={()=>{setMode(m);setEndpoint(m==='local'?'http://127.0.0.1:1235/v1':'https://api.openai.com/v1');setKey('');setShowKey(false);setClearKey(false);}}>{m==='local'?'本地模型':'云端 API'}</button>)}</div></div>
    <form className="model-settings-form" onSubmit={e=>{e.preventDefault();void save();}}>
    <div className="model-settings-grid" data-verified={testResult?.keyVerified?'true':'false'}>
      <div className="model-settings-main">
        <section className="model-config-block model-local" aria-label="本机模型服务">
          <div className="model-local-heading"><div><strong>本机模型服务</strong><span>检测已运行的服务，或启动内置 Qwen</span></div><button type="button" className="text-link" disabled={scanning||!host?.modelDiscover} onClick={()=>void scan()}>{scanning?'扫描中…':'重新扫描'}</button></div>
          {picks.length?<ul className="model-local-list">{picks.map(item=><li key={item.endpoint} className={item.endpoint===endpoint?'selected':''}>
            <div className="model-local-id"><strong>{item.label}</strong><small>{item.running?`${item.models.length} 个模型 · 端口 ${item.port}${item.models.length?` · ${item.models.slice(0,2).join('、')}${item.models.length>2?' 等':''}`:''}`:(item.note||'未启动')}</small></div>
            <button type="button" className="button secondary" disabled={busy||item.endpoint===endpoint} onClick={()=>void useService(item)}>{item.endpoint===endpoint?'使用中':item.running?'选用':'启动并选用'}</button>
          </li>)}</ul>:<p className="muted">{services&&scanning?'正在查看本机常用端口…':services?'没有检测到正在运行的本机服务。启动 LM Studio 或 Ollama 后点「重新扫描」，或在设置 → 通用里开启内置 Qwen。':'正在扫描本机…'}</p>}
        </section>
        <section className="model-config-block model-endpoint-block">
          <div className="model-config-heading"><div><strong>连接参数</strong><span>{local?'填写服务地址和模型名称':'填写云端兼容接口信息'}</span></div></div>
          {mode==='cloud'&&<div className="model-presets" role="group" aria-label="云端服务预设"><span>快速选择</span><button type="button" onClick={()=>{setEndpoint('https://api.openai.com/v1');setTestResult(null);setTestFeedback(null);}}>OpenAI</button><button type="button" onClick={()=>{setEndpoint('https://api.deepseek.com/v1');setTestResult(null);setTestFeedback(null);}}>DeepSeek</button><button type="button" onClick={()=>{setEndpoint('');setTestResult(null);setTestFeedback(null);}}>自定义</button></div>}
          <label>服务地址<input type="url" required value={endpoint} onChange={e=>{setEndpoint(e.target.value);setTestResult(null);setTestFeedback(null);if(e.target.value.startsWith('https://'))setMode('cloud');}} placeholder="https://api.example.com/v1" maxLength={500}/></label>
          <label>模型名称<input list="model-config-options" value={model} onChange={e=>{setModel(e.target.value);setTestResult(null);setTestFeedback(null);}} placeholder={modelOptions.length?'测试连接后选择，或手动输入':'留空后测试并读取模型'} maxLength={300}/><datalist id="model-config-options">{modelOptions.map(id=><option value={id} key={id}/>)}</datalist></label>
          {!local&&<label>API 密钥<div className="model-secret-field"><input type={showKey?'text':'password'} autoComplete="new-password" value={key} onChange={e=>{setKey(e.target.value);setTestResult(null);setTestFeedback(null);}} placeholder={config?.keyPresent&&endpoint===config.endpoint?'已安全保存；留空继续使用':'粘贴服务商 API 密钥'} maxLength={4096}/><button type="button" className="icon-button model-secret-toggle" onClick={()=>setShowKey(value=>!value)} aria-label={showKey?'隐藏 API 密钥':'查看 API 密钥'} title={showKey?'隐藏密钥明文，继续以圆点显示。':'暂时显示已输入的 API 密钥，方便核对后再保存。'}><>{showKey?<EyeOff size={15}/>:<Eye size={15}/>}</></button></div>{config?.keyPresent&&endpoint===config.endpoint&&!key&&<small className="model-field-help">密钥已保存在本机加密存储中；留空会继续使用它。</small>}{config?.keyPresent&&endpoint===config.endpoint&&!!key&&<small className="model-field-help">保存后将替换此前保存在本机的密钥。</small>}</label>}
          {config?.keyPresent&&endpoint===config.endpoint&&<button type="button" className="text-link model-secret-remove" disabled={busy||writesBlocked} onClick={()=>setConfirmAction({kind:'removeMainKey'})}>移除已保存的主连接密钥</button>}
          {!local&&<div className="model-remote-consent"><label className="inline-check"><input type="checkbox" checked={config?.endpoint===endpoint&&config.allowRemoteAttachments===true} disabled={busy||!host?.modelAttachmentsSet||writesBlocked||config?.endpoint!==endpoint} onChange={e=>void saveAttachments(e.target.checked)}/>允许附件发送到云端</label><p>{config?.endpoint!==endpoint?'保存此服务地址后，再为它单独设置附件授权。':config?.allowRemoteAttachments?'已开启对此服务的附件授权；每次发送前仍会展示内容供你检查并确认。':'默认关闭。开启后，每次发送仍需检查并确认附件内容。'} {config?.endpoint===endpoint?hostOf(endpoint):''}{config?.endpoint===endpoint?'；图片会本机按需缩小，OCR 文字也会发送。':''}</p></div>}
          {config?.secretUnavailable&&<p role="alert" className="save-error">无法读取本机已有密钥，已暂停修改配置以免覆盖它。请检查系统密钥存储后重新打开 Yuki。</p>}
          {config?.configUnavailable&&<p role="alert" className="save-error">配置文件无法读取，已暂停修改以避免覆盖原有数据。请检查配置文件后重新打开 Yuki。</p>}
          <div className="model-config-actions"><button type="button" className="button secondary" disabled={busy||!host?.modelTest} onClick={()=>void testConnection()}>{busy?'正在连接…':modelOptions.length?'重新测试并刷新模型':'测试连接并读取模型'}</button><button type="submit" className="button primary" disabled={busy||!host?.modelConfigSet||writesBlocked}>{busy?'处理中…':'保存配置'}</button>{error&&<p role="alert" className="save-error">{error}</p>}{message&&<p role="status" className="model-save-message">{message}</p>}</div>
          {testFeedback&&<div className={`model-test-feedback ${testFeedback.kind}`} role={testFeedback.kind==='auth'||testFeedback.kind==='network'||testFeedback.kind==='address'||testFeedback.kind==='response'?'alert':'status'}><strong>{testFeedback.title}</strong><p>{testFeedback.detail}</p>{testResult?.modelListed===false&&<small>当前输入的模型 ID 不在服务列表中；如它是服务端别名，可核对文档后仍尝试保存。</small>}{testResult?.keyVerified===false&&testResult?.listingAvailable&&<small>本次连接未验证 API 密钥。</small>}</div>}
          {config&&!config.keyPersistent&&<p className="model-field-help">当前系统加密不可用，密钥仅在本次运行保留。</p>}
          <p className="model-field-help">兼容 OpenAI Chat Completions（SSE）。云端必须使用 HTTPS。云端聊天会将你发送的对话内容交给所选服务。</p>
        </section>
      </div>
      <aside className="model-config-block model-profiles-block"><div className="model-config-heading"><div><strong>配置档案</strong><span>保存常用的服务地址和模型，可选加密保存密钥</span></div></div>
        <div className="model-profile-picker"><select aria-label="选择配置档案" value={profileId} disabled={busy||!config?.profiles?.length} onChange={e=>{const id=e.target.value;setProfileId(id);const profile=config?.profiles?.find(item=>item.id===id);setProfileName(profile?.name||'');setIncludeProfileKey(!!profile?.keyPresent);}}><option value="">选择已保存档案</option>{config?.profiles?.map(profile=><option value={profile.id} key={profile.id}>{profile.name}{profile.keyPresent?' · 含加密密钥':' · 未保存密钥'}</option>)}</select><button type="button" className="button secondary" disabled={busy||!profileId} onClick={()=>void useProfile()}>加载</button><button type="button" className="icon-button bordered" disabled={busy||!selectedProfile} onClick={()=>selectedProfile&&setConfirmAction({kind:'deleteProfile',id:selectedProfile.id,name:selectedProfile.name,endpoint:selectedProfile.endpoint,model:selectedProfile.model,keyPresent:selectedProfile.keyPresent})} aria-label="删除配置档案" title="移除此配置档案及其保存的连接信息；操作前会再次确认。"><Trash2 size={15}/></button></div>
        {selectedProfile&&<p className="model-profile-summary">{selectedProfile.endpoint} · {selectedProfile.model||'未设置模型'} · {selectedProfile.keyPresent?'此档案含本机加密密钥':'此档案不含密钥'}</p>}
        <div className="model-profile-save"><input aria-label="配置档案名称" value={profileName} onChange={e=>setProfileName(e.target.value)} placeholder="输入配置档案名称" maxLength={80}/><label className="inline-check"><input type="checkbox" checked={includeProfileKey} onChange={e=>setIncludeProfileKey(e.target.checked)}/>同时加密保存云端密钥</label><small className="model-field-help">不勾选时，档案不保存密钥；加载后需要重新输入。此档案密钥独立于主连接密钥。</small><div className="model-profile-actions"><button type="button" className="button secondary" disabled={busy||!profileName.trim()||writesBlocked} onClick={()=>requestProfileSave('new')}>保存为新档案</button><button type="button" className="button secondary" disabled={busy||!selectedProfile||writesBlocked} onClick={()=>requestProfileSave('update')}>更新所选档案</button></div></div>
      </aside>
    </div>
    </form>
    {confirmAction&&<div className="model-confirm-scrim" onMouseDown={event=>{if(event.target===event.currentTarget)setConfirmAction(null);}}><section className="model-confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="model-confirm-title"><strong id="model-confirm-title">{confirmAction.kind==='removeMainKey'?'移除主连接密钥？':confirmAction.kind==='deleteProfile'?'删除配置档案？':confirmAction.kind==='useProfile'?'加载不含密钥的档案？':'确认更新配置档案'}</strong>{confirmAction.kind==='removeMainKey'?<p>将从本机加密配置中移除当前云端主连接密钥。后续云端请求需要重新输入密钥；已保存到配置档案中的密钥不受影响。</p>:confirmAction.kind==='deleteProfile'?<><p>档案：{confirmAction.name}<br/>服务：{confirmAction.endpoint}<br/>模型：{confirmAction.model||'未设置'}<br/>密钥：{confirmAction.keyPresent?'档案密钥也会一并移除，不影响主连接密钥':'不含密钥'}</p><p>删除后不能从 Yuki 恢复；当前已加载的连接不会改变。</p></>:confirmAction.kind==='useProfile'?<p>档案：{confirmAction.name}<br/>服务：{confirmAction.endpoint}<br/>模型：{confirmAction.model||'未设置'}<br/>档案不含密钥。加载会移除当前主连接中已保存的密钥，之后需要重新输入。</p>:<><p>档案：{confirmAction.name}<br/>服务：{confirmAction.endpoint}<br/>模型：{confirmAction.model||'未设置'}<br/>密钥：{includeProfileKey?'更新后包含本机加密密钥':'更新后不包含密钥'}</p><pre>{confirmAction.diff}</pre></>}<div className="model-confirm-actions"><button type="button" className="button secondary" disabled={busy} onClick={()=>setConfirmAction(null)}>取消</button><button ref={confirmButtonRef} type="button" className="button primary" disabled={busy} onClick={()=>void confirm()}>{busy?'处理中…':confirmAction.kind==='removeMainKey'?'移除密钥':confirmAction.kind==='deleteProfile'?'确认删除':confirmAction.kind==='useProfile'?'加载档案':'确认更新'}</button></div></section></div>}
  </div>;
}

function errorText(value:unknown,secret:string){const raw=value instanceof Error?value.message:String(value);return secret?raw.split(secret).join('••••'):raw;}
