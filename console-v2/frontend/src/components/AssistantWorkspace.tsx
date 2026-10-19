import {useEffect,useRef,useState} from 'react';
import {Bot,MessageCircle,RefreshCw,Send,Square,Trash2} from './Icons';
import {host} from '../host';
import '../assistant.css';

type Turn={role:'user'|'assistant';content:string};
// Survives navigation between workbench pages, but is never written to disk.
let session:Turn[]=[];
let selectedModel='';
export function AssistantWorkspace(){
  const [messages,setMessages]=useState<Turn[]>(session),[draft,setDraft]=useState(''),[models,setModels]=useState<string[]>([]);
  const [model,setModel]=useState(selectedModel),[busy,setBusy]=useState(false),[connecting,setConnecting]=useState(false);
  const [error,setError]=useState(''),[phase,setPhase]=useState(''),[partial,setPartial]=useState('');
  const [endpoint,setEndpoint]=useState('127.0.0.1:1235');
  const active=useRef(''),end=useRef<HTMLDivElement>(null),mounted=useRef(true);
  const supported=!!host?.aiModels;
  async function connect(){
    if(!host?.aiModels)return;
    setConnecting(true);setError('');
    try{const result=await host.aiModels();if(!mounted.current)return;const list=result.models;setModels(list);setEndpoint(new URL(result.endpoint).host);
      const chosen=list.includes(selectedModel)?selectedModel:list.find(id=>/qwen3[._-]?8[-_ ]?4b/i.test(id))||'';
      setModel(chosen);selectedModel=chosen;
      if(!list.length)setError('服务已连接，但尚未发现模型。请在 LM Studio 加载已下载的模型。');
      else if(!chosen)setError('未自动匹配 Qwen3.8-4B，请在下方选择你要使用的模型。');
    }catch(e){if(mounted.current)setError(String(e instanceof Error?e.message:e));}
    finally{if(mounted.current)setConnecting(false);}
  }
  useEffect(()=>{
    mounted.current=true;void connect();
    const unsubscribe=host?.aiSubscribe?.(update=>{if(update.id===active.current){setPartial(update.text);setPhase(update.phase==='thinking'?'yuki 正在想一想…':'yuki 正在回复…');}});
    return ()=>{mounted.current=false;unsubscribe?.();if(active.current)void host?.aiCancel?.();};
  },[]);
  useEffect(()=>{end.current?.scrollIntoView({block:'nearest'});},[messages,partial,phase]);
  async function send(){
    const text=draft.trim();if(!text||busy||!model||!host?.aiChat)return;
    const next:Turn[]=[...session,{role:'user',content:text}];
    const previous=session;session=next;setMessages(next);setDraft('');setError('');setBusy(true);setPartial('');setPhase('yuki 正在想一想…');
    const id=crypto.randomUUID();active.current=id;
    // Keep a bounded history so the local model has room for a reply.
    let history=next.slice(-10);while(history.length>1&&history.reduce((n,item)=>n+item.content.length,0)>3800)history=history.slice(1);
    try{const result=await host.aiChat({id,model,messages:history});
      session=[...next,{role:'assistant',content:result.text}];if(mounted.current)setMessages(session);
    }catch(e){session=previous;if(mounted.current){setMessages(previous);setDraft(text);setError(String(e instanceof Error?e.message:e));}}
    finally{active.current='';if(mounted.current){setBusy(false);setPartial('');setPhase('');}}
  }
  return <div className="assistant-layout page-enter"><section className="card conversation live-conversation">
    <div className="card-heading"><span><MessageCircle size={17}/> 与雪对话</span><span className="subtle-badge">{busy?'正在交流':model?'本地模型':'等待连接'}</span></div>
    <div className="chat-transcript" aria-live="polite" aria-relevant="additions text">
      {!messages.length&&!busy?<div className="chat-empty"><div className="assistant-portrait"><img src="/pet-preview.png" alt="雪在等你说话"/></div><h2>Let me not to the marriage<br/>of true minds admit impediments.</h2><span className="poem-source">William Shakespeare · Sonnet 116</span><p>聊聊今天的小事，<br/>我在这里，听你说。</p><div className="suggestion-chips">{['今天过得怎么样？','陪我休息一会儿','介绍一下你自己'].map(text=><button key={text} disabled={!supported||busy} onClick={()=>setDraft(text)}>{text}</button>)}</div></div>:messages.map((item,i)=><div key={i} className={'chat-turn '+item.role}><span>{item.role==='user'?'你':'雪'}</span><p>{item.content}</p></div>)}
      {busy&&<div className="chat-turn assistant"><span>{phase}</span><p>{partial||'…'}</p></div>}<div ref={end}/>
    </div>
    {error&&<p className="save-error chat-error" role="alert">{error}</p>}
    <div className="chat-composer"><textarea aria-label="对话输入" value={draft} maxLength={2000} disabled={busy||!supported} onChange={e=>setDraft(e.target.value)} placeholder={model?'想对雪说些什么？':'连接本地模型后，开始聊天…'} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();void send();}}}/><div><span>Enter 发送 · Shift + Enter 换行</span>{busy?<button className="icon-button" aria-label="停止回复" onClick={()=>void host?.aiCancel?.()}><Square size={16}/></button>:<button className="icon-button" aria-label="发送消息" disabled={!draft.trim()||!model||!supported} onClick={()=>void send()}><Send size={18}/></button>}</div></div>
  </section><div className="stack"><section className="card"><div className="card-heading"><h3>本地对话引擎</h3><Bot size={18}/></div><p className="muted">LM Studio · 仅连接本机</p><label className="ai-model-label" htmlFor="ai-model">当前模型</label><select id="ai-model" className="ai-model-select" value={model} disabled={busy||!models.length} onChange={e=>{setModel(e.target.value);selectedModel=e.target.value;setError('');}}><option value="">选择模型</option>{models.map(id=><option key={id} value={id}>{id}</option>)}</select><div className="info-row"><span>服务地址</span><strong>{endpoint}</strong></div><div className="info-row"><span>对话记录</span><strong>仅本次运行保留</strong></div><div className="info-row"><span>联网 / 语音 / 工具</span><strong>未启用</strong></div><div className="ai-controls"><button className="button secondary" disabled={connecting||busy||!supported} onClick={()=>void connect()}><RefreshCw size={14} className={connecting?'spin':''}/>{connecting?'连接中':'重新连接'}</button><button className="icon-button bordered" title="新对话" aria-label="新对话" disabled={busy||!messages.length} onClick={()=>{session=[];setMessages([]);setError('');}}><Trash2 size={15}/></button></div>{!supported&&<p className="note">请使用 Electron 版 yuki 打开本地聊天。</p>}</section><section className="card"><h3>一点点熟悉你。</h3><p className="muted">雪会记住当前对话里你说过的话。切换页面后可以继续聊，退出软件后记录清除。</p><p className="note">首次回复需要加载模型，可能稍慢。模型思考内容不会作为聊天正文显示。</p></section></div></div>;
}
