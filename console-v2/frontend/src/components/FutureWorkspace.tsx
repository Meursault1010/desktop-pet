import { AssistantWorkspace } from './AssistantWorkspace';
import { ArrowUpRight, Bot, Circle, Clock3, Code2, FileText, Globe, MessageCircle, Mic, Play, Send, ShieldCheck, Sparkles } from './Icons';

export function FutureWorkspace({page,status}:{page:'assistant'|'tools';status:string}) {

  if(page==='assistant')return <AssistantWorkspace/>;
  const items=[{icon:Clock3,name:'读取当前时间',desc:'让回应与此刻自然相连。',level:'只读'},{icon:Play,name:'播放桌宠动作',desc:'用动作回应对话和情境。',level:'低风险'},{icon:Bot,name:'获取桌宠状态',desc:'了解 yuki 当前正在做什么。',level:'只读'},{icon:Globe,name:'打开指定网页',desc:'前往经过确认的网站。',level:'需要确认'},{icon:Code2,name:'读取项目状态',desc:'关注指定项目的工作进度。',level:'只读'},{icon:FileText,name:'读取指定文件',desc:'在授权范围内获取上下文。',level:'需要确认'}];
  return <div className="page-enter"><div className="tool-intro"><div><span className="eyebrow">工具能力预览</span><h2>从陪伴，到得力的小助手。</h2><p className="muted">为未来的快捷管理能力留出空间。</p></div><span className="subtle-badge"><ShieldCheck size={14}/>所有工具尚未注册</span></div><div className="tool-grid">{items.map(item=><section className="card tool-card" key={item.name}><div className="tool-card-top"><span className="tool-icon"><item.icon size={23}/></span></div><h3>{item.name}</h3><p className="muted">{item.desc}</p><div className="tool-meta"><span>{item.level}</span><span>未启用 · 暂无调用</span></div><button className="text-link" disabled>待接入<ArrowUpRight size={15}/></button></section>)}</div><div className="security-note"><ShieldCheck size={21}/><div><strong>能力有边界，陪伴更安心。</strong><p>未来工具通过白名单和权限检查接入，需要确认的操作会先询问你。当前页面不会读取文件、打开网站或执行命令。</p></div></div></div>;
}