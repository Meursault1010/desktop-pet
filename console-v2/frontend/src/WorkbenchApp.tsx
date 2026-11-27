import {WorkbenchInteractions} from './components/WorkbenchInteractions';
import {ThemePicker} from './components/ThemePicker';
import {SortableGroup} from './components/SortableGroup';
import {lazy,Suspense,useEffect,useRef,useState} from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import {LayoutGrid,Cat,Stars,Wrench,Settings2,Maximize2,Minimize2,Menu,X,Check,LoaderCircle,RefreshCw,ShieldCheck,AlertTriangle} from 'lucide-react';
import {defaults,demo} from './bridge';
import {host} from './host';
import {usePetController} from './usePetController';
import {useWorkbench} from './useWorkbench';
import {useScrollEdgeFeedback} from './useScrollEdgeFeedback';
import {useWorkbenchFeedback,workbenchSpring} from './useWorkbenchFeedback';
import {useNow} from './useNow';
import {SectionErrorBoundary} from './components/ErrorBoundary';
import {WorkspaceBoard} from './components/WorkspaceBoard';
import {CompanionStrip,Journal,Rhythm,SystemStatus,FocusTimer,Todos,ClipboardView} from './components/WorkbenchTools';
import {CharacterWorkspace} from './components/CharacterWorkspace';
import {ModelSettings} from './components/ModelSettings';
import {SelectionTranslation} from './components/SelectionTranslation';
import {LiveStatus} from './components/LiveStatus';
import {GeneralSettings,MemorySettings,ShortcutSettings,ThemeSettings} from './components/WorkbenchSettings';

import {readAppearance,writeAppearance} from './workbenchPreferences';
import type {WidgetType} from './workspaceModel';
import {workbenchLyrics} from './lyricPool';
import './workbench.css';
import './observatory.css';
import './workbench-v2.css';
import './workbench-v3.css';
import './workbench-v4.css';
import './workbench-startup.css';
const loadAssistant=()=>import('./components/AssistantWorkspace');
const AssistantWorkspace=lazy(()=>loadAssistant().then(module=>({default:module.AssistantWorkspace})));
const sections=[{id:'overview',name:'总览',icon:LayoutGrid},{id:'character',name:'角色',icon:Cat},{id:'assistant',name:'AI 助手',icon:Stars},{id:'tools',name:'工具',icon:Wrench},{id:'settings',name:'设置',icon:Settings2}] as const;
type Section=typeof sections[number]['id'];
const subtabs={character:{0:'随音乐舞动',2:'外观',3:'行为逻辑'},assistant:['与雪对话','模型配置'],tools:['时间管理','剪贴板','待办事项','划词翻译'],settings:['通用','主题与动态','快捷键','人设与记忆']} as const;
const pageSubtitles={overview:'宠物状态与今日记录',character:'音乐、外观与行为设置',assistant:'AI 对话与模型配置',tools:'专注、剪贴板、待办与翻译',settings:'通用、主题与快捷键设置'} as const;
export default function WorkbenchApp(){
 const [section,setSection]=useState<Section>('overview'),[tabs,setTabs]=useState({character:0,assistant:0,tools:0,settings:0}),[appearance,setAppearance]=useState(readAppearance),[appearanceReady,setAppearanceReady]=useState(!host?.workbenchConfig),[buttonHints,setButtonHints]=useState(true),[wide,setWide]=useState(false),[navOpen,setNavOpen]=useState(false),[dialog,setDialog]=useState<'exit'|'reset'|null>(null),[dialogError,setDialogError]=useState('');
 const pet=usePetController(),work=useWorkbench(section==='overview'||section==='character'||section==='tools'),pref=pet.state?.preferences??defaults,disabled=!pet.connected||pet.connecting;
 const [lyric,setLyric]=useState(()=>workbenchLyrics[Math.floor(Math.random()*workbenchLyrics.length)]);
 const [assistantOpened,setAssistantOpened]=useState(false);
 const [modelConnectionRevision,setModelConnectionRevision]=useState(0);
 useEffect(()=>{if(section==='assistant')setAssistantOpened(true);},[section]);
 useEffect(()=>{
  // Fetch the code during idle time, without opening history or contacting a model.
  if(typeof window.requestIdleCallback!=='function')return;
  const handle=window.requestIdleCallback(()=>{void loadAssistant().catch(()=>{});});
  return()=>window.cancelIdleCallback(handle);
 },[]);
 useEffect(()=>{const onVisibility=()=>{if(document.visibilityState==='visible')setLyric(workbenchLyrics[Math.floor(Math.random()*workbenchLyrics.length)]);};document.addEventListener('visibilitychange',onVisibility);return()=>document.removeEventListener('visibilitychange',onVisibility);},[]);
 const main=useRef<HTMLElement>(null);
 useWorkbenchFeedback(main,appearance.reduced);
 useEffect(()=>{let active=true;if(!host?.workbenchConfig)return;void host.workbenchConfig().then(c=>{if(active){setAppearance(a=>({...a,theme:c.theme,reduced:c.reduced}));setButtonHints(c.buttonHints!==false);}}).catch(e=>work.setError(String(e))).finally(()=>{if(active)setAppearanceReady(true);});return()=>{active=false;};},[]);

 useEffect(()=>{writeAppearance(appearance);if(appearanceReady)void host?.workbenchSet?.({theme:appearance.theme,reduced:appearance.reduced,buttonHints}).catch(e=>work.setError(String(e)));},[appearance,appearanceReady,buttonHints]);
 const focusRunning=useRef(false);
 useEffect(()=>{const running=!!work.focus.end,phase=work.focus.mode;const enabled=running&&phase==='focus';document.documentElement.dataset.focus=enabled?'true':'false';if(pet.connected){if(running){const remaining=Math.max(1,Math.ceil((work.focus.end!-Date.now())/1000));void pet.act('set_focus',{enabled:true,phase,remaining});}else if(focusRunning.current&&phase==='break'){void pet.act('set_focus',{enabled:true,phase:'break',remaining:work.focus.remaining});}else if(focusRunning.current||phase==='focus'){void pet.act('set_focus',{enabled:false});}}focusRunning.current=running;},[!!work.focus.end,work.focus.mode,pet.connected]);
 useEffect(()=>{setNavOpen(false);main.current?.scrollTo({top:0});},[section]);
 const petProps={state:pet.state,source:pet.source,disabled,act:pet.act,pref,setPreference:pet.setPreference};
 const tab=section==='overview'?0:tabs[section];
 useScrollEdgeFeedback(main,appearance.reduced,appearance.slow,`${section}:${tab}`);
 const startupPlayed=useRef(false);
 useEffect(()=>{
  if(!appearanceReady||startupPlayed.current||section!=='overview')return;
  const shell=main.current?.closest<HTMLElement>('.observatory');
  if(!shell)return;
  let frame=0,timer=0;
  const stop=()=>{
   window.cancelAnimationFrame(frame);
   window.clearTimeout(timer);
   delete shell.dataset.startupMotion;
  };
  const onVisibility=()=>{
   if(document.visibilityState!=='visible'){stop();return;}
   if(startupPlayed.current||!document.hasFocus())return;
   window.cancelAnimationFrame(frame);
   frame=window.requestAnimationFrame(()=>{
    if(document.visibilityState!=='visible'||!document.hasFocus())return;
    startupPlayed.current=true;
    if(appearance.reduced||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
    shell.dataset.startupMotion='true';
    timer=window.setTimeout(stop,680);
   });
  };
  document.addEventListener('visibilitychange',onVisibility);
  window.addEventListener('focus',onVisibility);
  onVisibility();
  return()=>{
   stop();
   document.removeEventListener('visibilitychange',onVisibility);
   window.removeEventListener('focus',onVisibility);
  };
 },[appearanceReady,appearance.reduced,section]);
 const previousPage=useRef({section,tab});
 useEffect(()=>{
  const sectionChanged=previousPage.current.section!==section;
  const previous=previousPage.current;
  const changed=sectionChanged||previousPage.current.tab!==tab;
  previousPage.current={section,tab};
  if(!changed)return;
  if(appearance.reduced||window.matchMedia('(prefers-reduced-motion: reduce)').matches)return;
  const content=main.current?.querySelector('.section-content');
  const heading=sectionChanged?main.current?.querySelector('.main-heading'):null;
  const shell=main.current?.closest('.observatory');
  const group=sectionChanged?shell?.querySelector('[data-sort-scope="main-navigation"]')
   :main.current?.querySelector('.subtabs > .sortable-navigation');
  const order=Array.from(group?.children??[],item=>item.getAttribute('data-sort-id'));
  const direction=Math.sign(
   order.indexOf(sectionChanged?section:String(tab))-order.indexOf(sectionChanged?previous.section:String(previous.tab)),
  )||1;
  const duration=appearance.slow?620:330;
  const offset=sectionChanged?`0 ${direction*16}px`:`${direction*12}px 0`;
  const headingMotion=heading?.animate([{opacity:.55,translate:`0 ${direction*9}px`},{opacity:1,translate:'0 0'}],{duration,easing:workbenchSpring});
  const contentMotion=content?.animate(
   [{opacity:.35,translate:offset},{opacity:1,offset:.55},{opacity:1,translate:'0 0'}],
   {duration,delay:sectionChanged?24:0,easing:appearance.slow?'cubic-bezier(.22,.61,.36,1)':workbenchSpring,fill:'backwards'},
  );
  return()=>{headingMotion?.cancel();contentMotion?.cancel();};
 },[section,tab,appearance.reduced,appearance.slow]);
 async function windowSize(){
  const next=!wide;
  setWide(next);
  try{
   await host?.windowMode?.(next,!appearance.reduced&&!window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  }catch(e){setWide(current=>current===next?!next:current);work.setError(String(e));}
 }
 function widget(type:WidgetType){switch(type){case 'companion':return <CompanionStrip work={work} pet={petProps}/>;case 'journal':return <Journal work={work} lyric={lyric}/>;case 'rhythm':return <Rhythm work={work} pet={petProps}/>;case 'system':return <SystemStatus work={work}/>;case 'focus':return <FocusTimer work={work}/>;case 'todos':return <Todos work={work} compact/>;case 'clipboard':return <ClipboardView work={work} compact/>;case 'translation':return <SelectionTranslation/>;}}
 const saved=<span className={'save-state '+(pet.failedKeys.length?'save-error':'')}>{pet.pending.length?<LoaderCircle className="spin" size={13}/>:<Check size={13}/>} {pet.saveLabel}</span>;
 return <div className={'observatory '+(wide?'is-wide':'is-compact')}><WorkbenchInteractions hints={buttonHints}/><a className="skip-link" href="#main-content">跳到主要内容</a><header className="window-bar"><div className="window-brand"><span>yuki</span><small>工作台</small></div><span className={'window-caption'+(demo?'':' lyric-quote')}>{demo?'界面预览 · 示例宠物状态':lyric.text}</span><LiveStatus state={pet.state} connected={pet.connected} connecting={pet.connecting}/><ThemePicker value={appearance.theme} disabled={!appearanceReady} onChange={theme=>setAppearance(a=>({...a,theme}))}/><button className="window-size" aria-label={wide?'切换紧凑窗口':'展开工作台'} onClick={()=>void windowSize()}>{wide?<Minimize2 size={14}/>:<Maximize2 size={14}/>}<span>{wide?'紧凑窗口':'展开工作台'}</span></button></header><aside className={'observatory-nav '+(navOpen?'open':'')}><nav aria-label="主导航"><SortableGroup scope="main-navigation" navigation sortable label="主栏目">{sections.map(s=><button key={s.id} title={s.name} aria-label={s.name} aria-current={section===s.id?'page':undefined} className={section===s.id?'active':''} onClick={()=>{setSection(s.id);setNavOpen(false);}}><s.icon size={19}/><span>{s.name}</span></button>)}</SortableGroup></nav><div className="nav-foot"><span><i className={pet.connected?'online-dot':''}/>{demo?'演示模式':pet.connected?'桌宠已连接':'等待连接'}</span><small>yuki · 冰银工作区</small></div></aside>{navOpen&&<button className="nav-scrim" aria-label="关闭导航" onClick={()=>setNavOpen(false)}/>}
 <main id="main-content" ref={main} data-section={section} tabIndex={-1}><div className="main-heading"><div className="main-heading-copy"><button className="icon-button mobile-nav" aria-label="切换导航" onClick={()=>setNavOpen(!navOpen)}><Menu size={19}/></button><div><h1>{sections.find(s=>s.id===section)?.name}</h1><p className="page-subtitle">{pageSubtitles[section]}</p></div></div><TodayLabel/></div>
 {!pet.connected&&!demo&&<div className="notice" role="status"><span>{pet.connecting?'正在连接桌宠…':pet.failure||'请通过 Electron 启动 Yuki，以使用桌面功能。'}</span><button disabled={pet.connecting} onClick={()=>void pet.retry()}><RefreshCw size={14}/>重新连接</button></div>}
 {demo&&<p className="preview-notice">界面预览 · 桌面功能需在应用中使用</p>}
 {work.error&&<div className="notice error" role="alert"><span>{work.error}</span><button onClick={()=>work.setError('')} aria-label="关闭错误提示"><X size={15}/></button></div>}
 {section!=='overview'&&<div className="subtabs" role="tablist" aria-label={sections.find(s=>s.id===section)?.name+'子页'}><SortableGroup key={section} scope={'tabs-'+section} navigation sortable label="子栏目">{Object.entries(subtabs[section]).map(([id,name])=>{const i=Number(id);return <button id={`tab-${section}-${i}`} role="tab" aria-controls={`panel-${section}`} aria-selected={tab===i} tabIndex={tab===i?0:-1} key={name} onClick={()=>setTabs(t=>({...t,[section]:i}))} onKeyDown={e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)||e.altKey||e.ctrlKey||e.metaKey)return;e.preventDefault();const tabs=Array.from(e.currentTarget.closest('[role="tablist"]')?.querySelectorAll<HTMLButtonElement>('[role="tab"]')||[]);const index=tabs.indexOf(e.currentTarget);const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:(index+(e.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;tabs[next]?.focus();tabs[next]?.click();}}>{name}</button>;})}</SortableGroup></div>}
 <div id={section==='overview'||section==='assistant'?undefined:`panel-${section}`} role={section==='overview'||section==='assistant'?undefined:'tabpanel'} aria-labelledby={section==='overview'||section==='assistant'?undefined:`tab-${section}-${tab}`} tabIndex={section==='overview'||section==='assistant'?undefined:-1} className="section-content">
 <SectionErrorBoundary key={section+':'+tab} section={section}>
 {section==='overview'&&<WorkspaceBoard render={widget}/>}
 {section==='character'&&<CharacterWorkspace tab={tab} pet={pet} work={work} lyric={lyric}/>}
 {section==='assistant'&&tab===1&&<section className="content-section connection-page"><h2>模型连接</h2><ModelSettings onSaved={()=>setModelConnectionRevision(value=>value+1)}/></section>}
 {section==='tools'&&<div className="subpage-motion" key={tab}>{tab===0&&<SortableGroup scope="time-panels" className="two-column"><section key="focus" className="content-section"><h2>专注计时</h2><FocusTimer work={work}/></section><section key="rhythm" className="content-section"><h2>休息提醒</h2><Rhythm work={work} pet={petProps}/><p className="muted">关闭工作台后继续计时；重启后恢复，错过的提醒不补发。</p></section></SortableGroup>}{tab===1&&<section className="content-section"><h2>最近的十次复制</h2><ClipboardView work={work}/></section>}{tab===2&&<section className="content-section"><h2>待办事项</h2><Todos work={work}/><p className="muted">事项保存在本机，一次性到时提醒需要 Yuki 保持运行。</p></section>}{tab===3&&<SelectionTranslation/>}</div>}
 {section==='settings'&&<div className="subpage-motion settings-v2" key={tab}>{tab===0&&<GeneralSettings pet={pet} work={work} buttonHints={buttonHints} onButtonHintsChange={setButtonHints} onReset={()=>setDialog('reset')} onExit={()=>setDialog('exit')}/ >}{tab===1&&<ThemeSettings appearance={appearance} onChange={setAppearance}/ >}{tab===2&&<ShortcutSettings/>}{tab===3&&<MemorySettings/>}</div>}
 </SectionErrorBoundary>
 <div hidden={section!=='assistant'||tab!==0} className="persistent-assistant">
  {(assistantOpened||section==='assistant')&&<SectionErrorBoundary section="assistant-chat">
   <Suspense fallback={<p className="muted" role="status">正在打开对话…</p>}>
    <AssistantWorkspace lyric={lyric} active={section==='assistant'&&tab===0} connectionRevision={modelConnectionRevision}/>
   </Suspense>
  </SectionErrorBoundary>}
 </div>
 </div><footer className="workbench-footer"><span><ShieldCheck size={13}/><span className="lyric-quote">{lyric.text}</span> <small>{lyric.artist} · {lyric.song} · {lyric.album} · {lyric.year}</small></span>{saved}</footer></main>
 {pet.notice&&!pet.notice.error&&<div className="toast" role="status"><span>{pet.notice.text}</span><button onClick={pet.dismissNotice} aria-label="关闭提示"><X size={16}/></button></div>}
 <Dialog.Root open={!!dialog||!!pet.notice?.error} onOpenChange={v=>{if(!v){setDialog(null);setDialogError('');pet.dismissNotice();}}}><Dialog.Portal><Dialog.Overlay className="dialog-overlay"/><Dialog.Content className="dialog-content"><div className="dialog-heading"><span className="dialog-icon error"><AlertTriangle size={18}/></span><Dialog.Title>{pet.notice?.error?'需要注意':dialog==='reset'?'恢复默认偏好？':'退出 Yuki？'}</Dialog.Title></div><Dialog.Description>{pet.notice?.text||(dialog==='reset'?'恢复宠物的大小、透明度与行为偏好。':'保存当前设置，然后关闭工作台和桌宠。')}</Dialog.Description>{dialogError&&<p role="alert" className="save-error">{dialogError}</p>}<div className="dialog-actions"><Dialog.Close className="button secondary">{pet.notice?.error?'知道了':'取消'}</Dialog.Close>{!pet.notice?.error&&<button className="button primary" onClick={async()=>{const ok=dialog==='reset'?await pet.act('reset_defaults'):await pet.exit();if(ok)setDialog(null);else setDialogError('操作未完成，请检查连接后重试。');}}>确认</button>}</div></Dialog.Content></Dialog.Portal></Dialog.Root>
 </div>;
}
function TodayLabel(){const now=useNow('day');return <span>{new Date(now).toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'})}</span>;}
