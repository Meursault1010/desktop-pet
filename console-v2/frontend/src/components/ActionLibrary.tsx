import { useEffect, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Search, Monitor, Square } from './Icons';
import { demo } from '../bridge';
import bundledCatalog from '../../public/actions/catalog.json';
import idleStates from '../../public/actions/idle-states.json';
import { loopPosition } from '../actionTimeline';
import './ActionLibrary.css';

type Action = {id:string; name:string; category:string; origin:string; frames:number; columns:number; cell:number; durations:number[]; loop_start?:number; atlas:string; poster:string; review:string; pixel_art?:boolean;tempo_profile?:string;idle_state?:string;idle_role?:string;idle_automatic?:boolean};
type Props = {initialId?:string;reduced?:boolean;disabled:boolean; visible:boolean; act:(name:string,payload?:Record<string,unknown>,success?:string)=>Promise<boolean>};

export function ActionLibrary({initialId,reduced=false,disabled,visible,act}:Props) {
  const actions: Action[] = bundledCatalog;
  const [selected,setSelected]=useState(actions.some(a=>a.id===initialId)?initialId!:actions[0]?.id||''),[query,setQuery]=useState(''),[stateFilter,setStateFilter]=useState('all');
  const [playing,setPlaying]=useState(!reduced&&!matchMedia('(prefers-reduced-motion: reduce)').matches),[loop,setLoop]=useState(true),[speed,setSpeed]=useState(1),[frame,setFrame]=useState(0),[error,setError]=useState(''),[pending,setPending]=useState(false);
  useEffect(()=>{const media=matchMedia('(prefers-reduced-motion: reduce)');const sync=()=>{if(reduced||media.matches)setPlaying(false);};sync();media.addEventListener('change',sync);return()=>media.removeEventListener('change',sync);},[reduced]);
  const canvas=useRef<HTMLCanvasElement>(null),image=useRef<HTMLImageElement|null>(null),position=useRef(0);
  const action=actions.find(a=>a.id===selected);
  useEffect(()=>{
    if(!action)return; let disposed=false;
    image.current=null; position.current=0;setFrame(0);setError('');
    const img=new Image();img.onload=()=>{if(disposed)return;if(img.width<Math.min(action.frames,action.columns)*action.cell||img.height<Math.ceil(action.frames/action.columns)*action.cell){setError('这组动作的图集尺寸无效或缺帧。');return;}image.current=img;};img.onerror=()=>{if(!disposed)setError('这组动作的图集加载失败。');};img.src='/'+action.atlas;
    return()=>{disposed=true;};
  },[action]);
  useEffect(()=>{
    if(!action)return;
    let request=0,last=0;
    const tick=(now:number)=>{
      const dt=last&&!document.hidden?Math.min(now-last,100):0;last=now;
      const total=action.durations.reduce((a,b)=>a+b,0);
      if(playing){position.current+=dt*speed;if(position.current>=total){if(loop)position.current=loopPosition(position.current,action.durations,action.loop_start);else{position.current=total-.001;setPlaying(false);}}}
      let elapsed=position.current,index=0;
      while(index<action.frames-1&&elapsed>=action.durations[index]){elapsed-=action.durations[index];index++;}
      setFrame(index);
      const ctx=canvas.current?.getContext('2d');
      if(ctx){ctx.imageSmoothingEnabled=!action.pixel_art;ctx.clearRect(0,0,256,256);if(image.current)ctx.drawImage(image.current,(index%action.columns)*256,Math.floor(index/action.columns)*256,256,256,0,0,256,256);}
      request=requestAnimationFrame(tick);
    };request=requestAnimationFrame(tick);return()=>cancelAnimationFrame(request);
  },[action,playing,loop,speed]);
  const available=actions.filter(a=>!(a as Action & {physics_only?:boolean}).physics_only);
  const groups=[{id:'all',name:'全部'},...idleStates.states,{id:'other',name:'其他动作'}];
  const inGroup=(a:Action,id:string)=>id==='all'||(id==='other'?!a.idle_state:a.idle_state===id);
  const filtered=available.filter(a=>inGroup(a,stateFilter)&&[a.name,a.category,a.idle_role].join(' ').includes(query.trim()));
  const currentState=idleStates.states.find(state=>state.id===action?.idle_state);
  const description=idleStates.states.find(state=>state.id===stateFilter)?.description
    ||(stateFilter==='other'?'点击、拖拽与情绪反应由互动触发，保留为独立动作。':'四种待机姿态，共用同一套桌面动作。睡觉遵循作息，清醒时随机安排站立、坐下与趴着。');
  const desktop=async(stop=false)=>{if(!action||pending)return;setPending(true);try{await act(stop?'stop_action':'play_action',stop?{}:{action_id:action.id,loop,speed},stop?'已恢复自然待机':'正在桌面播放：'+action.name);}finally{setPending(false);}};
  return <div className="action-library page-enter">
    <section className="card action-viewer">
      <div className="card-heading"><h2>{action?.name||'动作预览'}</h2><span className="subtle-badge">{action?.frames===1?'静态姿势':'逐帧动画'}</span></div>
      <p className="action-state-note"><span>{currentState?currentState.name+'待机':action?.category}</span>{action?.idle_role||'互动触发'}<small>{action?.idle_state==='sleep'?'作息与唤醒自动衔接':action?.id==='eat'?'用餐与零食日程安排':action?.idle_automatic?'参与随机待机':action?.idle_state==='stand'&&action.id==='blink'?'默认待机自带眨眼':'可手动播放'}</small></p>
      <div className="action-canvas-stage"><canvas ref={canvas} width={256} height={256} aria-label={action?.name+'动画预览'}/><span>本地预览 · 不影响桌面宠物</span></div>
      {error&&<p role="alert" className="save-error">{error}</p>}
      <div className="action-transport"><button className="icon-button bordered" aria-label={playing?'暂停预览':'播放预览'} onClick={()=>setPlaying(!playing)}>{playing?<Pause size={18}/>:<Play size={18}/>}</button><button className="icon-button bordered" aria-label="从头播放" onClick={()=>{position.current=0;setPlaying(true);}}><RotateCcw size={17}/></button><span>{frame+1} / {action?.frames||0} 帧</span><select aria-label="播放速度" value={speed} onChange={e=>setSpeed(Number(e.target.value))}>{[.25,.5,1,1.5,2].map(s=><option key={s} value={s}>{s}×</option>)}</select></div>
      <input className="action-scrubber" type="range" aria-label="逐帧查看" min={0} max={Math.max(0,(action?.frames||1)-1)} value={frame} onChange={e=>{const f=Number(e.target.value);setPlaying(false);setFrame(f);position.current=action?.durations.slice(0,f).reduce((a,b)=>a+b,0)||0;}}/>
      <label className="action-loop"><input type="checkbox" checked={loop} onChange={e=>setLoop(e.target.checked)}/>循环播放</label>
      <details className="action-material"><summary>素材信息 · {((action?.durations.reduce((a,b)=>a+b,0)||0)/1000).toFixed(2)} 秒</summary><p className="muted">{action?.tempo_profile&&<>节奏：{action.tempo_profile}（1× 为推荐速度）。<br/></>}{action?.origin==='generated'?'参考原图新生成':'已有素材转换'} · {action?.review}</p></details>
      <div className="action-desktop"><button className="button primary" disabled={disabled||!visible||!action||pending||demo} onClick={()=>void desktop()}><Monitor size={16}/>在桌面播放</button><button className="button secondary" disabled={disabled||pending||demo} onClick={()=>void desktop(true)}><Square size={15}/>恢复待机</button></div>
      <p className="action-help">{demo?'界面预览模式不控制真实宠物。':!visible?'请先在“总览”显示 yuki。':action?.idle_state==='sleep'?'这里播放睡眠动作素材；持续睡眠与唤醒仍由作息系统控制。':'手动动作不会改动安静模式、移动偏好或默认呼吸待机。'}</p>
    </section>
    <section className="action-browser"><div className="action-search"><Search size={18}/><input aria-label="搜索动作" placeholder="搜索动作或待机姿态…" value={query} onChange={e=>setQuery(e.target.value)}/><span aria-live="polite">{filtered.length} 项</span></div><div className="action-categories" role="group" aria-label="待机状态分类">{groups.map(group=><button className={stateFilter===group.id?'selected':''} aria-pressed={stateFilter===group.id} data-idle-state={group.id} key={group.id} onClick={()=>setStateFilter(group.id)}>{group.name}<span>{available.filter(a=>inGroup(a,group.id)).length}</span></button>)}</div><p className="action-state-description">{description}</p><div className="action-grid">{filtered.map(a=><button key={a.id} data-action-id={a.id} className={`action-tile ${a.id===selected?'selected':''}`} aria-pressed={a.id===selected} onClick={()=>{setSelected(a.id);setPlaying(!reduced&&!matchMedia('(prefers-reduced-motion: reduce)').matches);}}><img loading="lazy" src={'/'+a.poster} alt=""/><strong>{a.name}</strong><small>{a.idle_state?idleStates.states.find(s=>s.id===a.idle_state)?.name+'待机':a.category} · {a.idle_role||'互动反应'}</small></button>)}</div>{!filtered.length&&<p className="muted">没有匹配的动作。试试其他分类或更短的关键词。</p>}</section>
  </div>;
}
