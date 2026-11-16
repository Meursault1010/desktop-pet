import {Fragment,memo,useCallback,useEffect,useRef,useState} from 'react';
import {Bot,RefreshCw,Send,Square,Trash2} from './Icons';
import {host} from '../host';
import type {AttachmentMode,AttachmentReview,ChatAttachment,ConversationSnapshot,ReasoningEffort,ModelConfigSnapshot} from '../host/types';
import {Paperclip,X,FileText,Pencil,Plus,PanelLeft} from 'lucide-react';
import {parseMarkdown} from '../markdown';
import type {Inline} from '../markdown';
import '../assistant.css';
import '../desktop.css';
import type {WorkbenchLyric} from '../lyricPool';
import {workbenchLyrics} from '../lyricPool';

type Turn={id:string;role:'user'|'assistant';content:string;attachments?:string[];files?:ChatAttachment[]};
type PendingAttachmentReview={review:AttachmentReview;text:string;files:ChatAttachment[];base:Turn[];candidate:Turn[];omittedIds:string[]};
function boundedHistory(history:Turn[]){let bounded=history.slice(-10);while(bounded.length>1&&bounded.reduce((n,item)=>n+item.content.length,0)>3800)bounded=bounded.slice(1);return bounded;}
function readableError(value:unknown){
  const raw=value instanceof Error?value.message:String(value);
  return raw.replace(/^Error invoking remote method '[^']+':\s*(?:Error:\s*)?/,'');
}
function connectionError(value:unknown,endpoint:string){
  const raw=readableError(value),lower=raw.toLowerCase();
  if(/模型服务返回\s*401|\b401\b/.test(raw))return `连接失败：服务拒绝了 API 密钥（401）。请检查密钥是否正确、是否已过期，以及它是否属于 ${endpoint}。`;
  if(/模型服务返回\s*403|\b403\b/.test(raw))return `连接失败：服务禁止访问（403）。请确认账号有权使用这个服务或模型。`;
  if(/模型服务返回\s*404|\b404\b/.test(raw))return `连接失败：找不到这个服务地址（404）。请检查地址是否包含正确的 /v1，或确认模型服务是否支持 OpenAI 兼容接口。`;
  if(/模型服务返回\s*429|\b429\b/.test(raw))return '连接失败：请求太频繁或额度已用尽（429）。请稍后再试，或检查云端服务额度。';
  if(/模型服务返回\s*5\d\d|\b5\d\d\b/.test(raw))return `连接失败：模型服务暂时不可用（${raw.match(/\b5\d\d\b/)?.[0]||'服务器错误'}）。请稍后再试或查看服务状态。`;
  if(/fetch failed|econnrefused|连接被拒绝|网络|timeout|超时|未连接模型服务/i.test(`${raw} ${lower}`))return `连接失败：无法访问 ${endpoint}。如果使用本地模型，请先启动 LM Studio/Ollama 并确认端口；如果使用云端，请检查网络和 HTTPS 地址。`;
  if(/尚未发现模型|加载模型/.test(raw))return `连接成功，但没有找到可聊天的模型。请在 ${endpoint} 中加载一个聊天模型，不要选择 embedding 模型。`;
  return `连接失败：${(raw||'模型服务没有给出具体原因').replace(/[。．]+$/,'')}。请检查服务地址、模型名称和 API 密钥。`;
}
// Mirrors the persisted conversation while the workbench is open: the module copy keeps
// page switches instant, the main process owns what survives a restart.
let session:Turn[]=[];
let selectedModel='';
function storedMessages(value:ConversationSnapshot):Turn[]{
  return value.messages.map(item=>({id:item.id,role:item.role,content:item.content,attachments:item.attachments,files:item.files?.map(file=>({...file,truncated:false}))}));
}
function renderInlines(tokens:Inline[],keyBase:string){
  return tokens.map((token,index)=>{
    if(token.link){const link=token.link;return <a key={keyBase+index} href={link} onClick={event=>{event.preventDefault();void host?.openExternal?.(link);}} title={link}>{token.text}</a>;}
    if(token.code)return <code key={keyBase+index}>{token.text}</code>;
    if(token.bold)return <strong key={keyBase+index}>{token.text}</strong>;
    return token.text;
  });
}
function MessageBody({text}:{text:string}){
  const blocks=parseMarkdown(text);
  if(!blocks.length)return <div className="chat-body"><p>{' '}</p></div>;
  return <div className="chat-body">
    {blocks.map((block,index)=><Fragment key={index}>
      {block.kind==='paragraph'&&<p>{renderInlines(block.inlines,`p${index}`)}</p>}
      {block.kind==='heading'&&<p className={`md-heading level-${block.level}`}>{renderInlines(block.inlines,`h${index}`)}</p>}
      {block.kind==='list'&&(block.ordered
        ?<ol className="md-list md-ordered">{block.items.map((item,i)=><li key={i}>{renderInlines(item,`l${index}${i}`)}</li>)}</ol>
        :<ul className="md-list">{block.items.map((item,i)=><li key={i}>{renderInlines(item,`l${index}${i}`)}</li>)}</ul>)}
      {block.kind==='code'&&<pre className="md-code"><code>{block.lines.join('\n')}</code></pre>}
    </Fragment>)}
  </div>;
}
function toStored(messages:Turn[]){
  return messages.map(item=>({id:item.id,role:item.role,content:item.content,
    ...(item.attachments?.length?{attachments:item.attachments}: {}),
    ...(item.files?.length?{files:item.files.map(file=>({id:file.id,name:file.name,size:file.size,kind:file.kind,characters:file.characters}))}: {})}));
}
// Rows are memoised so a streaming frame only re-renders the bubble that is still arriving;
// the callbacks it receives are stable, and read live values through a ref.
type TurnRowProps={item:Turn;last:boolean;busy:boolean;ready:boolean;onCopy:(text:string)=>void;onRegenerate:(id:string)=>void;onRemove:(id:string)=>void};
const TurnRow=memo(function TurnRow({item,last,busy,ready,onCopy,onRegenerate,onRemove}:TurnRowProps){
  return <div className={'chat-turn '+item.role}><span>{item.role==='user'?'你':'雪'}</span><MessageBody text={item.content}/>
    {!!item.files?.length&&<div className="chat-file-list">{item.files.map(file=><span className="chat-file" key={file.id}>{file.preview?<img src={file.preview} alt={file.name}/>:<FileText size={18}/>}<span>{file.name}</span></span>)}</div>}
    <div className="chat-turn-actions">
      <button type="button" aria-label="复制这条消息" onClick={()=>onCopy(item.content)}>复制</button>
      {item.role==='assistant'&&last&&!busy&&<button type="button" aria-label="重新生成这条回答" disabled={!ready} onClick={()=>onRegenerate(item.id)}>重新生成</button>}
      <button type="button" className="danger" aria-label="删除这条消息" disabled={busy} onClick={()=>onRemove(item.id)}>删除</button>
    </div>
  </div>;
});
export function AssistantWorkspace({lyric=workbenchLyrics[0]}:{lyric?:WorkbenchLyric}){
  const [messages,setMessages]=useState<Turn[]>(session),[draft,setDraft]=useState(''),[models,setModels]=useState<string[]>([]);
  const [model,setModel]=useState(selectedModel),[busy,setBusy]=useState(false),[connecting,setConnecting]=useState(false);
  const [error,setError]=useState(''),[connectionMessage,setConnectionMessage]=useState(''),[phase,setPhase]=useState(''),[partial,setPartial]=useState('');
  const [endpoint,setEndpoint]=useState('127.0.0.1:1235');
  const [historyOpen,setHistoryOpen]=useState(false);
  const [modelConfig,setModelConfig]=useState<ModelConfigSnapshot|null>(null),[reasoningEffort,setReasoningEffort]=useState<ReasoningEffort>('auto'),[reasoningBusy,setReasoningBusy]=useState(false);
  const [files,setFiles]=useState<ChatAttachment[]>([]),[attaching,setAttaching]=useState(false);
  const [attachmentReview,setAttachmentReview]=useState<PendingAttachmentReview|null>(null);
  const [attachmentChecking,setAttachmentChecking]=useState(false);
  const [retry,setRetry]=useState<null|{kind:'send'}|{kind:'regenerate';id:string}>(null);
  const historyToggleRef=useRef<HTMLButtonElement>(null),historyPanelRef=useRef<HTMLElement>(null);
  async function addFiles(){if(!host?.aiAttach)return;setAttachmentReview(null);setAttaching(true);setError('');try{const added=await host.aiAttach();if(mounted.current){if(files.length+added.length>4)setError('每条消息最多 4 个附件，请先移除部分附件');else setFiles(previous=>[...previous,...added]);}}catch(e){if(mounted.current)setError(readableError(e));}finally{if(mounted.current)setAttaching(false);}}
  async function changeMode(id:string,mode:AttachmentMode){
    if(!host?.aiAttachMode)return;
    setAttachmentReview(null);
    setError('');
    try{const saved=await host.aiAttachMode(id,mode);if(mounted.current)setFiles(list=>list.map(item=>item.id===id?{...item,imageMode:saved.imageMode}:item));}
    catch(e){if(mounted.current)setError(readableError(e));}
  }
  const active=useRef(''),end=useRef<HTMLDivElement>(null),mounted=useRef(true);
  const supported=!!host?.aiModels;
  const [snapshot,setSnapshot]=useState<ConversationSnapshot|null>(null),[renaming,setRenaming]=useState(''),[renameValue,setRenameValue]=useState('');
  const activeId=useRef('');
  const stored=!!host?.conversations&&!!host?.conversationStore;
  const persistenceLabel=!supported?'当前环境不可用':!stored?'会话记录不可用':snapshot?.persistence===false?'仅保留在本次运行':snapshot?'保存在本机':'正在读取';
  function apply(value:ConversationSnapshot|null){
    if(!value)return;
    setAttachmentReview(null);
    setSnapshot(value);activeId.current=value.activeId;setRetry(null);
    session=storedMessages(value);if(mounted.current){setMessages(session);setStick(true);}
  }
  useEffect(()=>{
    if(!host?.conversations)return;let live=true;
    host.conversations().then(value=>{if(live)apply(value);}).catch(e=>{if(live)setError(readableError(e));});
    return()=>{live=false;};
  },[]);
  // The transcript is only written once a reply lands, so a failed send leaves no half turn behind.
  async function persist(next:Turn[]){
    session=next;if(mounted.current)setMessages(next);
    if(!host?.conversationStore)return;
    try{const value=await host.conversationStore({id:activeId.current,messages:toStored(next)});if(value){setSnapshot(value);activeId.current=value.activeId;}}
    catch(e){if(mounted.current)setError(readableError(e));}
  }
  async function newConversation(){
    if(!host?.conversationNew){session=[];setMessages([]);setError('');return;}
    setError('');try{apply(await host.conversationNew());}catch(e){setError(readableError(e));}
  }
  async function openConversation(id:string){
    if(!host?.conversationOpen||id===activeId.current)return;
    setError('');try{apply(await host.conversationOpen(id));}catch(e){setError(readableError(e));}
  }
  async function renameConversation(id:string,value:string){
    if(!host?.conversationRename||!value.trim())return;
    setError('');setRenaming('');
    try{const next=await host.conversationRename(id,value);if(next)setSnapshot(next);}
    catch(e){setError(readableError(e));}
  }
  async function deleteConversation(id:string){
    if(!host?.conversationDelete)return;
    setError('');try{apply(await host.conversationDelete(id));}catch(e){setError(readableError(e));}
  }
  async function clearConversations(){
    if(!host?.conversationsClear){session=[];setMessages([]);setError('');return;}
    setError('');try{apply(await host.conversationsClear());}catch(e){setError(readableError(e));}
  }
  async function setPersistence(enabled:boolean){
    if(!host?.conversationsPersistence)return;
    setError('');
    try{const next=await host.conversationsPersistence(enabled);if(next)setSnapshot(next);}
    catch(e){setError(readableError(e));}
  }
  async function connect(){
    if(!host?.aiModels)return;
    setConnecting(true);setError('');setConnectionMessage('正在连接模型服务…');
    try{const result=await host.aiModels();if(!mounted.current)return;const list=result.models;setModels(list);setEndpoint(new URL(result.endpoint).host);void host.modelConfig?.().then(value=>{if(mounted.current){setModelConfig(value);setReasoningEffort(value.reasoningEffort||'auto');}}).catch(()=>{});
      const chosen=list.includes(result.preferredModel||'')?result.preferredModel!:list.includes(selectedModel)?selectedModel:list.find(id=>/qwen3[._-]?8[-_ ]?4b/i.test(id))||list[0]||'';
      setAttachmentReview(null);setModel(chosen);selectedModel=chosen;
      if(!list.length){setConnectionMessage('连接成功，但没有找到可聊天的模型。请先在模型服务中加载一个聊天模型。');return;}
      setConnectionMessage('');
      
    }catch(e){if(mounted.current){setConnectionMessage('');setError(connectionError(e,endpoint));}}
    finally{if(mounted.current)setConnecting(false);}
  }
  useEffect(()=>{
    mounted.current=true;void connect();
    void host?.modelConfig?.().then(value=>{if(mounted.current){setModelConfig(value);setReasoningEffort(value.reasoningEffort||'auto');}}).catch(()=>{});
    const unsubscribe=host?.aiSubscribe?.(update=>{if(update.id===active.current){setPartial(update.text);setPhase(update.phase==='thinking'?'yuki 正在想一想…':'yuki 正在回复…');}});
    return ()=>{mounted.current=false;unsubscribe?.();if(active.current)void host?.aiCancel?.();};
  },[]);
  useEffect(()=>{
    if(!historyOpen)return;
    historyPanelRef.current?.querySelector<HTMLElement>('button:not(:disabled),input:not(:disabled)')?.focus();
    const onKeyDown=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();setHistoryOpen(false);}};
    window.addEventListener('keydown',onKeyDown);
    return()=>{window.removeEventListener('keydown',onKeyDown);historyToggleRef.current?.focus();};
  },[historyOpen]);
  async function changeReasoningEffort(value:ReasoningEffort){
    if(!host?.modelConfigSet||!modelConfig||!modelConfig.endpoint.startsWith('https:'))return;
    const previous=reasoningEffort;setReasoningEffort(value);setReasoningBusy(true);setError('');
    try{const next=await host.modelConfigSet({endpoint:modelConfig.endpoint,model:modelConfig.model,reasoningEffort:value});setModelConfig(next);setReasoningEffort(next.reasoningEffort||value);}
    catch(e){setReasoningEffort(previous);setError(readableError(e));}
    finally{if(mounted.current)setReasoningBusy(false);}
  }
  const [stick,setStick]=useState(true),transcript=useRef<HTMLDivElement>(null);
  useEffect(()=>{if(stick)end.current?.scrollIntoView({block:'nearest'});},[messages,partial,phase,stick]);
  function trackScroll(){
    const el=transcript.current;if(!el)return;
    const atBottom=el.scrollHeight-el.scrollTop-el.clientHeight<80;
    if(atBottom!==stick)setStick(atBottom);
  }
  const live=useRef({model,busy});live.current={model,busy};
  async function requestReply(history:Turn[],attachmentApproval?:string,omittedIds:string[]=[]){
    if(!host?.aiChat||!live.current.model)throw new Error('请先连接模型服务');
    const id=crypto.randomUUID();active.current=id;
    setBusy(true);setPartial('');setPhase('yuki 正在想一想…');setStick(true);
    // Keep a bounded history so the local model has room for a reply.
    const bounded=boundedHistory(history),omitted=new Set(omittedIds);
    const messages=bounded.map(({role,content,attachments})=>({role,content,...(attachments?.length?{attachments:attachments.filter(value=>!omitted.has(value))}:{})})).map(item=>item.attachments?.length?item:{role:item.role,content:item.content});
    try{const result=await host.aiChat({id,model:live.current.model,messages,...(attachmentApproval?{attachmentApproval}:{})});return result.text;}
    finally{active.current='';if(mounted.current){setBusy(false);setPartial('');setPhase('');}}
  }
  async function completeSend(next:Turn[],text:string,sentFiles:ChatAttachment[],attachmentApproval?:string,omittedIds:string[]=[],filesToKeep:ChatAttachment[]=[]){
    const previous=session;session=next;setMessages(next);setDraft('');setFiles(filesToKeep);setAttachmentReview(null);setError('');setRetry(null);setStick(true);
    try{const answer=await requestReply(next,attachmentApproval,omittedIds);void persist([...next,{id:crypto.randomUUID(),role:'assistant',content:answer}]);}
    catch(e){session=previous;if(mounted.current){setMessages(previous);setDraft(text);setFiles(sentFiles);setAttachmentReview(null);setRetry({kind:'send'});setError(readableError(e));}}
  }
  async function send(){
    const text=draft.trim()||(files.length?'请识别并说明这些附件的内容。':'');if(!text||busy||attachmentChecking||attaching||!model||!host?.aiChat)return;
    const sentFiles=files;
    const next:Turn[]=[...session,{id:crypto.randomUUID(),role:'user',content:text,...(sentFiles.length?{attachments:sentFiles.map(f=>f.id),files:sentFiles}: {})}];
    const requestContext=boundedHistory(next),ids=[...new Set(requestContext.flatMap(item=>item.attachments||[]))];
    setError('');
    if(ids.length&&host.aiAttachmentReview){
      const selectedModelAtReview=model,base=session;setAttachmentChecking(true);
      try{const review=await host.aiAttachmentReview(ids,selectedModelAtReview);if(base!==session||selectedModelAtReview!==live.current.model)return;if(review.remote){setAttachmentReview({review,text,files:sentFiles,base,candidate:next,omittedIds:[]});return;}}
      catch(e){setError(readableError(e));return;}
      finally{setAttachmentChecking(false);}
    }else if(ids.length&&modelConfig?.endpoint.startsWith('https:')){setError('当前版本无法检查云端附件内容，已阻止发送。请更新工作台后重试。');return;}
    await completeSend(next,text,sentFiles);
  }
  async function confirmAttachmentSend(){
    const pending=attachmentReview;if(!pending||busy)return;
    if(session!==pending.base||live.current.model!==pending.review.model){setAttachmentReview(null);setError('对话或模型已变化，请重新检查附件后发送。');return;}
    setError('');
    try{
      const ids=pending.review.items.map(item=>item.id);
      const ticket=ids.length?await host?.aiAttachmentApprove?.(pending.review.reviewId,ids,live.current.model):undefined;
      if(ids.length&&!ticket)throw new Error('无法确认附件发送，请重新检查。');
      await completeSend(pending.candidate,pending.text,pending.files,ticket?.ticket,pending.omittedIds,pending.files.length?[]:pending.files);
    }catch(e){const message=readableError(e);if(/检查已失效|内容已变化|服务设置已变化|附件授权/.test(message))setAttachmentReview(null);setError(message);}
  }
  function removeReviewedAttachment(id:string){
    const current=attachmentReview;if(!current)return;
    const filesLeft=current.files.filter(item=>item.id!==id),last=current.candidate[current.candidate.length-1];
    const candidate=[...current.candidate.slice(0,-1),{...last,...(filesLeft.length?{attachments:filesLeft.map(item=>item.id),files:filesLeft}:{attachments:undefined,files:undefined})}];
    setFiles(list=>list.filter(item=>item.id!==id));
    setAttachmentReview({...current,files:filesLeft,candidate,review:{...current.review,items:current.review.items.filter(item=>item.id!==id)},omittedIds:[...current.omittedIds,id]});
  }
  async function sendTextOnly(){
    const pending=attachmentReview;if(!pending)return;
    const omittedIds=[...new Set([...pending.review.items.map(item=>item.id),...pending.omittedIds])];
    const filesLeft=pending.files;
    const last=pending.candidate[pending.candidate.length-1];
    const candidate=[...pending.candidate.slice(0,-1),{...last,attachments:undefined,files:undefined}];
    await completeSend(candidate,pending.text,filesLeft,undefined,omittedIds,filesLeft);
  }
  // Regenerating replaces the last answer in place: the stored turn count stays the same and
  // the context we send never contains the answer being replaced.
  async function regenerate(id:string){
    if(live.current.busy||!live.current.model||!host?.aiChat)return;
    const index=session.findIndex(item=>item.id===id);
    const kept=session.slice(0,index);
    if(index<1||session.length-1!==index||kept[kept.length-1]?.role!=='user'){setError('只能重新生成最后一条回答。');return;}
    setError('');setRetry(null);
    try{const answer=await requestReply(kept);void persist([...kept,{id:crypto.randomUUID(),role:'assistant',content:answer}]);}
    catch(e){if(mounted.current){setRetry({kind:'regenerate',id});setError(readableError(e));}}
  }
  async function copyMessage(text:string){
    setError('');
    try{await navigator.clipboard.writeText(text);}
    catch{if(mounted.current)setError('无法写入剪贴板，请手动选中文字复制。');}
  }
  async function removeMessage(id:string){
    if(live.current.busy)return;setError('');await persist(session.filter(item=>item.id!==id));
  }
  const onCopy=useCallback((text:string)=>{void copyMessage(text);},[]);
  const onRegenerate=useCallback((id:string)=>{void regenerate(id);},[]);
  const onRemove=useCallback((id:string)=>{void removeMessage(id);},[]);
  function retryFailed(){
    if(!retry)return;
    if(retry.kind==='send')void send();else void regenerate(retry.id);
  }
  const activeTitle=snapshot?.sessions.find(item=>item.id===snapshot.activeId)?.title;
  const history=<>
    <button type="button" className="assistant-history-scrim" aria-label="关闭历史对话" onClick={()=>setHistoryOpen(false)}/>
    <aside ref={historyPanelRef} id="assistant-history-panel" className={'assistant-history'+(historyOpen?' is-open':'')} aria-label="历史对话">
      <div className="assistant-history-head"><span>最近对话</span><button type="button" className="icon-button" aria-label="新对话" title="新建一段独立对话；当前对话会保留在历史列表中。" disabled={busy} onClick={()=>{void newConversation();setHistoryOpen(false);}}><Plus size={17}/></button></div>
      <div className="assistant-history-list">
        {stored&&snapshot?.sessions.map(item=><div className={'assistant-history-item'+(item.id===snapshot.activeId?' selected':'')} key={item.id}>
          {renaming===item.id
            ?<input className="chat-session-edit" aria-label="对话标题" autoFocus value={renameValue} maxLength={40} onChange={e=>setRenameValue(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'){e.preventDefault();void renameConversation(item.id,renameValue);}if(e.key==='Escape')setRenaming('');}} onBlur={()=>void renameConversation(item.id,renameValue)}/>
            :<button type="button" className="assistant-history-select" aria-current={item.id===snapshot.activeId?'page':undefined} onClick={()=>{void openConversation(item.id);setHistoryOpen(false);}} title={new Date(item.updatedAt).toLocaleString('zh-CN')}><span>{item.title}</span><small>{item.count} 条消息</small></button>}
          <div className="assistant-history-actions"><button type="button" className="icon-button" aria-label="重命名对话" title="修改这段对话在历史列表中的标题，不会改动消息内容。" onClick={()=>{setRenaming(item.id);setRenameValue(item.title);}}><Pencil size={13}/></button><button type="button" className="icon-button" aria-label="删除对话" title="永久删除这段对话及其中的消息，无法撤销。" disabled={busy} onClick={()=>void deleteConversation(item.id)}><Trash2 size={13}/></button></div>
        </div>)}
        {!snapshot?.sessions.length&&<p className="assistant-history-empty">新对话会显示在这里。</p>}
      </div>
      {(snapshot?.sessions.length||0)>1&&<button type="button" className="assistant-history-clear" disabled={busy} onClick={()=>void clearConversations()}>清空全部对话</button>}
      <div className="assistant-history-foot">对话记录 · {persistenceLabel}</div>
    </aside>
  </>;
  return <div className="assistant-workspace page-enter"><div className={'assistant-layout'+(historyOpen?' history-open':'')}>
    {history}
    <section className="card conversation live-conversation">
    <header className="assistant-toolbar">
      <div className="assistant-toolbar-left"><button ref={historyToggleRef} type="button" className="assistant-history-toggle" aria-label="查看历史对话" aria-expanded={historyOpen} aria-controls="assistant-history-panel" title="展开或收起最近对话列表，可切换、重命名或删除已保存的聊天。" onClick={()=>setHistoryOpen(v=>!v)}><PanelLeft size={17}/></button><div className="assistant-current"><div className="assistant-current-title">{activeTitle||'新对话'}</div><div className="assistant-current-meta"><span className={'assistant-state-dot'+(models.length?' connected':'')}/><span>{busy?'正在回复':connecting?'正在连接':model?'已连接':models.length?'选择模型':'未连接'}</span></div></div></div>
    </header>
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{busy?phase:''}</div>
    <div className="chat-transcript" ref={transcript} onScroll={trackScroll}>
      {!messages.length&&!busy?<div className="chat-empty"><div className="assistant-portrait"><img src="/pet-preview.png" alt="雪"/></div><span className="assistant-empty-lyric">{lyric.text}<small>{lyric.artist} · {lyric.song}</small></span><h2>想和雪聊些什么？</h2><p>聊聊今天，也可以发来图片或文档。</p><div className="suggestion-chips">{['今天过得怎么样？','陪我休息一会儿','介绍一下你自己'].map(text=><button key={text} disabled={!supported||busy} onClick={()=>setDraft(text)}>{text}</button>)}</div></div>:messages.map((item,i)=><TurnRow key={item.id} item={item} last={i===messages.length-1} busy={busy} ready={!!model&&supported} onCopy={onCopy} onRegenerate={onRegenerate} onRemove={onRemove}/>)}
      {busy&&<div className="chat-turn assistant"><span>{phase}</span><div className="chat-body"><p>{partial||'…'}</p></div></div>}<div ref={end}/>
      {!stick&&<button type="button" className="chat-jump" onClick={()=>{setStick(true);end.current?.scrollIntoView({block:'nearest'});}}>回到最新</button>}
    </div>
    {(error||connectionMessage)&&<p className={(error?'chat-error save-error ':'')+'connection-feedback'} role={error?'alert':'status'}>{error||connectionMessage}{error&&retry&&<span className="chat-retry-row"><button type="button" className="text-link chat-retry" disabled={busy||!model||!supported} onClick={retryFailed}><RefreshCw size={12}/>重试</button><small>{retry.kind==='send'?'会把你刚写的内容原样再发一次':'会用同一条提问替换刚才的回答'}</small></span>}</p>}
    <div className="chat-composer">
      {attachmentReview&&<section className="chat-attachment-review" aria-label="云端附件发送检查">
        <div className="chat-attachment-review-head"><strong>发送前检查</strong><span>附件尚未发送</span></div>
        <p className="chat-attachment-destination">{attachmentReview.review.authorized?'以下内容将发送到':'云端附件授权尚未开启：以下内容不会发送到'} <b>{attachmentReview.review.endpointHost}</b> · {attachmentReview.review.model}</p>
        {attachmentReview.review.items.length>0?<div className="chat-attachment-review-list">{attachmentReview.review.items.map(item=><article className="chat-attachment-review-item" key={item.id}>
          <div className="chat-attachment-review-file">{item.imagePreview?<img src={item.imagePreview} alt={`待检查的图片：${item.name}`}/>:<FileText size={17}/>}<div><strong>{item.name}</strong><small>{item.kind==='image'?'图片': '文档'} · {(item.size/1024).toFixed(0)} KB{item.imageIncluded?' · 图片会发送（最长边最多 1536 px）':''}{item.kind==='image'&&!item.imageIncluded?' · 图片不会发送':''}{item.textIncluded?` · 提取文字 ${item.characters||0} 字符${item.truncated?'（已截取）':''}`:''}</small></div><button type="button" className="text-link" disabled={busy} onClick={()=>removeReviewedAttachment(item.id)}>本次移除</button></div>
          {item.textIncluded&&!!item.textPreview&&<details className="chat-attachment-text-preview"><summary>查看本次发送的提取文字（{item.characters||item.textPreview.length} 字符）</summary><pre>{item.textPreview}{item.truncated?'\n[实际请求会标明：内容已截取]':''}</pre></details>}
        </article>)}</div>:<p className="muted">本次不会发送附件，只发送对话文字。</p>}
        {!attachmentReview.review.authorized&&<p className="chat-attachment-blocked" role="alert">请先到「AI 助手 → 模型配置」为此服务开启附件授权。开启后需要重新检查本次发送。</p>}
        <div className="chat-attachment-review-actions"><button type="button" className="button secondary" disabled={busy} onClick={()=>setAttachmentReview(null)}>返回编辑</button><button type="button" className="button secondary" disabled={busy} onClick={()=>void sendTextOnly()}>仅发送文字</button><button type="button" className="button primary" disabled={busy||!attachmentReview.review.authorized} onClick={()=>void confirmAttachmentSend()}>{busy?'发送中…':attachmentReview.review.items.length?'确认并发送附件':'发送消息'}</button></div>
        <small className="chat-attachment-review-note">过去对话中仍保留在上下文里的附件也会再次发送；可在此逐项移除。Yuki 不审核接收方的数据处理方式。</small>
      </section>}
      {!!files.length&&<div className="chat-file-list composer-attachments" aria-label="待发送附件">{files.map(file=><div className="chat-file" key={file.id}>{file.preview?<img src={file.preview} alt={file.name}/>:<FileText size={18}/>}<span title={file.name}>{file.name}<small>{file.kind==='image'?`图片 · ${file.characters?`OCR 提取 ${file.characters} 字符`:'未识别到文字'}`:`${file.characters} 字符${file.truncated?' · 已截取':''}`}</small></span>{file.kind==='image'&&<select className="chat-file-mode" aria-label={`${file.name} 的发送方式`} value={file.imageMode||'both'} disabled={busy||attachmentChecking||!!attachmentReview||!host?.aiAttachMode} onChange={e=>void changeMode(file.id,e.target.value as AttachmentMode)}><option value="both">文字 + 图片</option><option value="text">只发文字</option><option value="image">只发图片</option></select>}<button className="icon-button" disabled={busy||attachmentChecking||!!attachmentReview} aria-label={`移除 ${file.name}`} onClick={()=>{setAttachmentReview(null);setFiles(list=>list.filter(f=>f.id!==file.id));}}><X size={14}/></button></div>)}</div>}
      <textarea aria-label="对话输入" value={draft} maxLength={2000} disabled={!supported||attachmentChecking} onChange={e=>{setAttachmentReview(null);setDraft(e.target.value);}} placeholder={model?'想对雪说些什么？':'连接模型后，开始聊天…'} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing&&!busy){e.preventDefault();void send();}}}/>
      <div className="chat-composer-tools"><div className="composer-left"><button className="icon-button" title="添加图片或文档" aria-label="添加图片或文档" disabled={busy||attachmentChecking||!!attachmentReview||attaching||!host?.aiAttach||files.length>=4} onClick={()=>void addFiles()}><Paperclip size={17}/></button><span>{attaching?'正在读取附件…':attachmentChecking?'正在检查附件…':'Enter 发送 · Shift + Enter 换行'}</span></div><div className="composer-right">
        <label className="composer-model"><span className="sr-only">当前模型</span><select aria-label="当前模型" value={model} disabled={busy||attachmentChecking||!models.length} onChange={e=>{setAttachmentReview(null);setModel(e.target.value);selectedModel=e.target.value;setError('');}}><option value="">选择模型</option>{models.map(id=><option key={id} value={id}>{id}</option>)}</select></label>
        {modelConfig?.endpoint.startsWith('https:')&&<label className="reasoning-inline"><span>思考</span><select aria-label="思考程度" value={reasoningEffort} disabled={busy||reasoningBusy||!host?.modelConfigSet} onChange={e=>void changeReasoningEffort(e.target.value as ReasoningEffort)}><option value="auto">自动</option><option value="low">低</option><option value="medium">中</option><option value="high">高</option></select></label>}
        {busy?<button className="icon-button composer-send" aria-label="停止回复" title="中止雪当前生成的回复；已经显示的内容会保留。" onClick={()=>void host?.aiCancel?.()}><Square size={16}/></button>:<button className="icon-button composer-send" aria-label={attachmentChecking?'正在检查附件':'发送消息'} title={attachmentChecking?'正在检查附件内容及发送方式…':attachmentReview?'完成附件发送前检查后即可发送。':'发送输入内容和已添加附件，Enter 也可直接发送。'} disabled={attachmentChecking||!!attachmentReview||(!draft.trim()&&!files.length)||attaching||!model||!supported} onClick={()=>void send()}><Send size={18}/></button>}
      </div></div>
    </div>
  </section>
  </div>
  </div>;
}
