import {ThemePicker} from './components/ThemePicker';
import {SortableGroup} from './components/SortableGroup';
import {useEffect,useRef,useState} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {LayoutGrid,Cat,Stars,Wrench,Settings2,Maximize2,Minimize2,Menu,X,Check,LoaderCircle,RefreshCw,ShieldCheck} from 'lucide-react';
import {defaults,demo} from './bridge';
import {host} from './host';
import {usePetController} from './usePetController';
import {useWorkbench} from './useWorkbench';
import {useNow} from './useNow';
import {SectionErrorBoundary} from './components/ErrorBoundary';
import {WorkspaceBoard} from './components/WorkspaceBoard';
import {CompanionStrip,Journal,Rhythm,Media,SystemStatus,FocusTimer,Todos,ClipboardView} from './components/WorkbenchTools';
import {CharacterWorkspace} from './components/CharacterWorkspace';
import {AssistantWorkspace} from './components/AssistantWorkspace';
import {ModelSettings} from './components/ModelSettings';
import {SelectionTranslation} from './components/SelectionTranslation';
import {GeneralSettings,MemorySettings,ShortcutSettings,ThemeSettings} from './components/WorkbenchSettings';
import {WorkspaceStars} from './components/StarField';
import {readAppearance,writeAppearance} from './workbenchPreferences';
import type {WidgetType} from './workspaceModel';
import {workbenchLyrics} from './lyricPool';
import './workbench.css';
import './observatory.css';
import './workbench-v2.css';
const sections=[{id:'overview',name:'总览',icon:LayoutGrid},{id:'character',name:'角色',icon:Cat},{id:'assistant',name:'AI 助手',icon:Stars},{id:'tools',name:'工具',icon:Wrench},{id:'settings',name:'设置',icon:Settings2}] as const;
type Section=typeof sections[number]['id'];
const subtabs={character:['音乐互动','动作','外观','行为逻辑'],assistant:['与雪对话','模型连接'],tools:['时间管理','剪贴板','待办事项','划词翻译'],settings:['通用','主题与动态','快捷键','人设与记忆']} as const;
export default function WorkbenchApp(){
 const [section,setSection]=useState<Section>('overview'),[tabs,setTabs]=useState({character:0,assistant:0,tools:0,settings:0}),[appearance,setAppearance]=useState(readAppearance),[appearanceReady,setAppearanceReady]=useState(!host?.workbenchConfig),[wide,setWide]=useState(false),[navOpen,setNavOpen]=useState(false),[dialog,setDialog]=useState<'exit'|'reset'|null>(null),[dialogError,setDialogError]=useState('');
 const pet=usePetController(),work=useWorkbench(section==='overview'||section==='character'||section==='tools'),pref=pet.state?.preferences??defaults,disabled=!pet.connected||pet.connecting;
 const [lyric,setLyric]=useState(()=>workbenchLyrics[Math.floor(Math.random()*workbenchLyrics.length)]);
 useEffect(()=>{const onVisibility=()=>{if(document.visibilityState==='visible')setLyric(workbenchLyrics[Math.floor(Math.random()*workbenchLyrics.length)]);};document.addEventListener('visibilitychange',onVisibility);return()=>document.removeEventListener('visibilitychange',onVisibility);},[]);
 const main=useRef<HTMLElement>(null);
 useEffect(()=>{let active=true;if(!host?.workbenchConfig)return;void host.workbenchConfig().then(c=>{if(active)setAppearance(a=>({...a,theme:c.theme,reduced:c.reduced,particles:c.particles}));}).catch(e=>work.setError(String(e))).finally(()=>{if(active)setAppearanceReady(true);});return()=>{active=false;};},[]);
 useEffect(()=>{writeAppearance(appearance);if(appearanceReady)void host?.workbenchSet?.({theme:appearance.theme,reduced:appearance.reduced,particles:appearance.particles}).catch(e=>work.setError(String(e)));},[appearance,appearanceReady]);
 useEffect(()=>{const enabled=!!work.focus.end&&work.focus.mode==='focus';document.documentElement.dataset.focus=enabled?'true':'false';if(pet.connected)void pet.act('set_focus',{enabled});},[!!work.focus.end,work.focus.mode,pet.connected]);
 useEffect(()=>{setNavOpen(false);main.current?.scrollTo({top:0});},[section]);
 const petProps={state:pet.state,source:pet.source,disabled,act:pet.act,pref,setPreference:pet.setPreference};
 const tab=section==='overview'?0:tabs[section];
 async function windowSize(){try{const result=await host?.windowMode?.(!wide);setWide(result?.wide??!wide);}catch(e){work.setError(String(e));}}
 function widget(type:WidgetType){switch(type){case 'companion':return <CompanionStrip work={work} pet={petProps}/>;case 'journal':return <Journal work={work} lyric={lyric}/>;case 'rhythm':return <Rhythm work={work} pet={petProps}/>;case 'media':return <Media work={work} lyric={lyric}/>;case 'system':return <SystemStatus work={work}/>;case 'focus':return <FocusTimer work={work}/>;case 'todos':return <Todos work={work} compact/>;case 'clipboard':return <ClipboardView work={work} compact/>;case 'translation':return <SelectionTranslation/>;}}
 const saved=<span className={'save-state '+(pet.failedKeys.length?'save-error':'')}>{pet.pending.length?<LoaderCircle className="spin" size={13}/>:<Check size={13}/>} {pet.saveLabel}</span>;
 return <div className={'observatory '+(wide?'is-wide':'is-compact')}><a className="skip-link" href="#main-content">跳到主要内容</a><header className="window-bar"><div className="window-brand"><span>yuki</span><small>工作台</small></div><span className="window-caption">{demo?'界面预览 · 示例宠物状态':lyric.text}</span><ThemePicker value={appearance.theme} disabled={!appearanceReady} onChange={theme=>setAppearance(a=>({...a,theme}))}/><button className="window-size" aria-label={wide?'切换紧凑窗口':'展开工作台'} onClick={()=>void windowSize()}>{wide?<Minimize2 size={14}/>:<Maximize2 size={14}/>}<span>{wide?'紧凑窗口':'展开工作台'}</span></button></header><aside className={'observatory-nav '+(navOpen?'open':'')}><nav aria-label="主导航"><SortableGroup scope="main-navigation" navigation label="主栏目">{sections.map(s=><button key={s.id} title={s.name} aria-label={s.name} aria-current={section===s.id?'page':undefined} className={section===s.id?'active':''} onClick={()=>setSection(s.id)}><s.icon size={19}/><span>{s.name}</span></button>)}</SortableGroup></nav><div className="nav-foot"><span><i className={pet.connected?'online-dot':''}/>{demo?'演示模式':pet.connected?'桌宠已连接':'等待连接'}</span><small>yuki · 冰银工作区</small></div></aside>{navOpen&&<button className="nav-scrim" aria-label="关闭导航" onClick={()=>setNavOpen(false)}/>}
 <main id="main-content" ref={main} tabIndex={-1}><WorkspaceStars/><div className="main-heading"><div><button className="icon-button mobile-nav" aria-label="切换导航" onClick={()=>setNavOpen(!navOpen)}><Menu size={19}/></button><h1>{sections.find(s=>s.id===section)?.name}</h1></div><TodayLabel/></div>
 {!pet.connected&&!demo&&<div className="notice" role="status"><span>{pet.connecting?'正在连接桌宠…':pet.failure||'请通过 Electron 启动 Yuki，以使用桌面功能。'}</span><button disabled={pet.connecting} onClick={()=>void pet.retry()}><RefreshCw size={14}/>重新连接</button></div>}
 {demo&&<p className="preview-notice">浏览器设计预览 · 系统、模型和剪贴板需在 Electron 中使用，当前不生成虚假监测数据。</p>}
 {(work.error||work.storageError)&&<div className="notice error" role="alert"><span>{work.error||work.storageError}</span><button onClick={()=>work.setError('')} aria-label="关闭错误提示"><X size={15}/></button></div>}
 {section!=='overview'&&<div className="subtabs" role="tablist" aria-label={sections.find(s=>s.id===section)?.name+'子页'}><SortableGroup key={section} scope={'tabs-'+section} navigation label="子栏目">{subtabs[section].map((name,i)=><button role="tab" aria-selected={tab===i} key={name} onClick={()=>setTabs(t=>({...t,[section]:i}))}>{name}</button>)}</SortableGroup></div>}
 <div className="section-content">
 <SectionErrorBoundary key={section+':'+tab} section={section}>
 {section==='overview'&&<WorkspaceBoard render={widget}/>}
 {section==='character'&&<CharacterWorkspace tab={tab} pet={pet} work={work} reduced={appearance.reduced} lyric={lyric}/>}
 {section==='assistant'&&tab===1&&<section className="content-section connection-page"><h2>连接你选择的模型。</h2><p className="muted">本地模型与云端 API 共用一个连接，保存后用于聊天和桌面快捷对话。</p><ModelSettings expanded/><p className="muted">本地：LM Studio / Ollama 的兼容接口。云端：HTTPS 地址、模型名称和 API 密钥。文档解析与 OCR 在本机完成；云端聊天会将你发送的文字和附件内容交给所选服务。</p></section>}
 {section==='tools'&&<div className="subpage-motion" key={tab}>{tab===0&&<SortableGroup scope="time-panels" className="two-column"><section key="focus" className="content-section"><h2>给眼前的事，一段完整的时间。</h2><FocusTimer work={work}/></section><section key="rhythm" className="content-section"><h2>休息，也是计划的一部分。</h2><Rhythm work={work} pet={petProps}/><p className="muted">切页与隐藏工作台时保持计时；退出后停止通知，重新打开按结束时间恢复。</p></section></SortableGroup>}{tab===1&&<section className="content-section"><h2>最近的十次复制</h2><ClipboardView work={work}/></section>}{tab===2&&<section className="content-section"><h2>一步一步，把今天安排好。</h2><Todos work={work}/><p className="muted">事项保存在本机，一次性到时提醒需要 Yuki 保持运行。</p></section>}{tab===3&&<SelectionTranslation/>}</div>}
 {section==='settings'&&<div className="subpage-motion settings-v2" key={tab}>{tab===0&&<GeneralSettings pet={pet} work={work} onReset={()=>setDialog('reset')} onExit={()=>setDialog('exit')}/ >}{tab===1&&<ThemeSettings appearance={appearance} onChange={setAppearance}/ >}{tab===2&&<ShortcutSettings/>}{tab===3&&<MemorySettings/>}</div>}
 </SectionErrorBoundary>
 <div hidden={section!=='assistant'||tab!==0} className="persistent-assistant"><SectionErrorBoundary section="assistant-chat"><AssistantWorkspace lyric={lyric}/></SectionErrorBoundary></div>
 </div><footer className="workbench-footer"><span><ShieldCheck size={13}/>{lyric.text} <small>{lyric.artist} · {lyric.song} · {lyric.album} · {lyric.year}</small></span>{saved}</footer></main>
 {pet.notice&&<div className={'toast '+(pet.notice.error?'toast-error':'')} role="status"><span>{pet.notice.text}</span><button onClick={pet.dismissNotice} aria-label="关闭提示"><X size={16}/></button></div>}
 <Dialog.Root open={!!dialog||!!work.reminder} onOpenChange={v=>{if(!v){setDialog(null);work.setReminder('');setDialogError('');}}}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="dialog-content"><Dialog.Title>{work.reminder?'雪的小提醒':dialog==='reset'?'恢复默认偏好？':'结束今天的陪伴？'}</Dialog.Title><Dialog.Description>{work.reminder||(dialog==='reset'?'恢复宠物的大小、透明度与行为偏好。':'保存当前设置，然后关闭工作台和桌宠。')}</Dialog.Description>{dialogError&&<p role="alert" className="save-error">{dialogError}</p>}<div className="dialog-actions"><Dialog.Close className="button secondary">{work.reminder?'知道了':'取消'}</Dialog.Close>{!work.reminder&&<button className="button primary" onClick={async()=>{const ok=dialog==='reset'?await pet.act('reset_defaults'):await pet.exit();if(ok)setDialog(null);else setDialogError('操作未完成，请检查连接后重试。');}}>确认</button>}</div></Dialog.Content></Dialog.Portal></Dialog.Root>
 </div>;
}
function TodayLabel(){const now=useNow();return <span>{new Date(now).toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'})}</span>;}


