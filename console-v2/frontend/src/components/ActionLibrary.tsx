import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Play, Pause, RotateCcw, Search, Monitor, Square } from './Icons';
import { demo } from '../bridge';
import bundledCatalog from '../../public/actions/catalog.json';
import idleStates from '../../public/actions/idle-states.json';
import { loopPosition } from '../actionTimeline';
import './ActionLibrary.css';

type Action = {id:string; name:string; category:string; origin:string; frames:number; columns:number; cell:number; durations:number[]; loop_start?:number; atlas:string; poster:string; review:string; pixel_art?:boolean;tempo_profile?:string;idle_state?:string;idle_role?:string;idle_automatic?:boolean;physics_only?:boolean};
type Props = {initialId?:string;reduced?:boolean;disabled:boolean; visible:boolean; act:(name:string,payload?:Record<string,unknown>,success?:string)=>Promise<boolean>};

const actions = bundledCatalog as Action[];
const actionById = new Map(actions.map(action => [action.id, action]));
const durationById = new Map(actions.map(action => [action.id, action.durations.reduce((sum, value) => sum + value, 0)]));
const idleById = new Map(idleStates.states.map(state => [state.id, state]));
const groups = [{id:'all',name:'全部'},...idleStates.states,{id:'other',name:'其他动作'},{id:'system',name:'抛出与碰撞'}];
const groupCounts = Object.fromEntries(groups.map(group => [group.id, actions.filter(action => inGroup(action, group.id)).length])) as Record<string, number>;
let browse = {selected:'',query:'',filter:'all'};

function inGroup(action: Action, id: string) {
  if (id === 'all') return true;
  if (id === 'system') return !!action.physics_only;
  if (id === 'other') return !action.idle_state && !action.physics_only;
  return action.idle_state === id;
}

function prefersReduced() {
  return matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function frameIndexAt(position: number, action: Action) {
  let elapsed = position;
  let index = 0;
  while (index < action.frames - 1 && elapsed >= action.durations[index]) {
    elapsed -= action.durations[index];
    index++;
  }
  return index;
}

const ActionTile = memo(function ActionTile({action,selected,onSelect}:{action:Action;selected:boolean;onSelect:(id:string)=>void}) {
  const state = action.idle_state ? idleById.get(action.idle_state) : undefined;
  return <button data-action-id={action.id} className={'action-tile '+(selected?'selected':'')} aria-pressed={selected} onClick={()=>onSelect(action.id)}>
    <img loading="lazy" src={'/'+action.poster} alt=""/>
    <strong>{action.name}</strong>
    <small>{state?state.name+'待机':action.category} · {action.idle_role||'互动反应'}</small>
  </button>;
});

const ActionBrowser = memo(function ActionBrowser({selected,onSelect}:{selected:string;onSelect:(id:string)=>void}) {
  const [query,setQuery]=useState(browse.query),[stateFilter,setStateFilter]=useState(browse.filter);
  useEffect(()=>{browse.query=query;browse.filter=stateFilter;},[query,stateFilter]);
  const filtered=useMemo(()=>{
    const needle=query.trim().toLowerCase();
    return actions.filter(action=>inGroup(action,stateFilter)&&(!needle||[action.name,action.category,action.idle_role].join(' ').toLowerCase().includes(needle)));
  },[query,stateFilter]);
  const description=idleById.get(stateFilter)?.description
    ||(stateFilter==='other'?'点击、拖拽与情绪反应由互动触发，保留为独立动作。':'四种待机姿态，共用同一套桌面动作。睡觉遵循作息，清醒时随机安排站立、坐下与趴着。');
  return <section className="action-browser">
    <div className="action-search"><Search size={18}/><input aria-label="搜索动作" placeholder="搜索动作或待机姿态…" value={query} onChange={e=>setQuery(e.target.value)}/><span aria-live="polite">{filtered.length} 项</span></div>
    <div className="action-categories" role="group" aria-label="待机状态分类">{groups.map(group=><button className={stateFilter===group.id?'selected':''} aria-pressed={stateFilter===group.id} data-idle-state={group.id} key={group.id} onClick={()=>setStateFilter(group.id)}>{group.name}<span>{groupCounts[group.id]??0}</span></button>)}</div>
    <p className="action-state-description">{description}</p>
    <div className="action-grid">{filtered.map(action=><ActionTile key={action.id} action={action} selected={action.id===selected} onSelect={onSelect}/>)}</div>
    {!filtered.length&&<p className="muted">没有匹配的动作。试试其他分类或更短的关键词。</p>}
  </section>;
});

export function ActionLibrary({initialId,reduced=false,disabled,visible,act}:Props) {
  const [selected,setSelected]=useState(()=>actions.some(action=>action.id===initialId)?initialId!:browse.selected&&actionById.has(browse.selected)?browse.selected:actions[0]?.id||'');
  const [playing,setPlaying]=useState(()=>!reduced&&!prefersReduced());
  const [loop,setLoop]=useState(true),[speed,setSpeed]=useState(1),[frame,setFrame]=useState(0),[error,setError]=useState(''),[pending,setPending]=useState(false);
  const canvas=useRef<HTMLCanvasElement>(null),image=useRef<HTMLImageElement|null>(null),position=useRef(0),frameRef=useRef(0);
  const reducedRef=useRef(reduced);
  reducedRef.current=reduced;
  const action=actionById.get(selected);
  const params=useRef({action,loop,speed});
  params.current={action,loop,speed};

  const draw=useCallback((index:number)=>{
    const ctx=canvas.current?.getContext('2d'),current=params.current.action;
    if(!ctx||!current)return;
    ctx.imageSmoothingEnabled=!current.pixel_art;
    ctx.clearRect(0,0,256,256);
    if(image.current)ctx.drawImage(image.current,(index%current.columns)*current.cell,Math.floor(index/current.columns)*current.cell,current.cell,current.cell,0,0,256,256);
  },[]);

  useEffect(()=>{const media=matchMedia('(prefers-reduced-motion: reduce)');const sync=()=>{if(reduced||media.matches)setPlaying(false);};sync();media.addEventListener('change',sync);return()=>media.removeEventListener('change',sync);},[reduced]);

  useEffect(()=>{
    if(!action)return; let disposed=false;
    image.current=null; position.current=0; frameRef.current=0; setFrame(0); setError('');
    draw(0);
    const img=new Image();
    img.decoding='async';
    img.onload=()=>{
      if(disposed)return;
      if(img.width<Math.min(action.frames,action.columns)*action.cell||img.height<Math.ceil(action.frames/action.columns)*action.cell){setError('这组动作的图集尺寸无效或缺帧。');return;}
      image.current=img; draw(frameRef.current);
    };
    img.onerror=()=>{if(!disposed)setError('这组动作的图集加载失败。');};
    img.src='/'+action.atlas;
    return()=>{disposed=true;img.onload=null;img.onerror=null;};
  },[action,draw]);

  useEffect(()=>{
    if(!playing)return;
    let request=0,last=performance.now(),lastUi=0;
    const tick=(now:number)=>{
      const current=params.current.action;
      if(!current)return;
      const dt=last&&!document.hidden?Math.min(now-last,100):0; last=now;
      const total=durationById.get(current.id)??0;
      let next=position.current+dt*params.current.speed;
      if(next>=total){
        if(params.current.loop)next=loopPosition(next,current.durations,current.loop_start);
        else{next=total-.001;position.current=next;const index=frameIndexAt(next,current);frameRef.current=index;draw(index);setFrame(index);setPlaying(false);return;}
      }
      position.current=next;
      const index=frameIndexAt(next,current);
      if(index!==frameRef.current){frameRef.current=index;draw(index);}
      if(now-lastUi>=100){lastUi=now;setFrame(index);}
      request=requestAnimationFrame(tick);
    };
    request=requestAnimationFrame(tick);
    return()=>cancelAnimationFrame(request);
  },[playing,draw]);

  const select=useCallback((id:string)=>{
    browse.selected=id; position.current=0; frameRef.current=0; setSelected(id); setFrame(0);
    setPlaying(!reducedRef.current&&!prefersReduced());
  },[]);
  const togglePlay=()=>{if(playing)setFrame(frameRef.current);setPlaying(!playing);};
  const reset=()=>{position.current=0;frameRef.current=0;setFrame(0);draw(0);setPlaying(true);};
  const scrub=(value:number)=>{if(!action)return;const start=action.durations.slice(0,value).reduce((sum,duration)=>sum+duration,0);position.current=start;frameRef.current=value;setPlaying(false);setFrame(value);draw(value);};

  const currentState=action?.idle_state?idleById.get(action.idle_state):undefined;
  const totalSeconds=((action?durationById.get(action.id):0)||0)/1000;
  const desktop=async(stop=false)=>{if(!action||pending||action.physics_only&&!stop)return;setPending(true);try{await act(stop?'stop_action':'play_action',stop?{}:{action_id:action.id,loop,speed},stop?'已恢复自然待机':'正在桌面播放：'+action.name);}finally{setPending(false);}};
  return <div className="action-library page-enter">
    <section className="card action-viewer">
      <div className="card-heading"><h2>{action?.name||'动作预览'}</h2><span className="subtle-badge">{action?.frames===1?'静态姿势':'逐帧动画'}</span></div>
      <p className="action-state-note"><span>{currentState?currentState.name+'待机':action?.category}</span>{action?.idle_role||'互动触发'}<small>{action?.idle_state==='sleep'?'作息与唤醒自动衔接':action?.id==='eat'?'用餐与零食日程安排':action?.id==='dragged'?'真实拖动时触发':action?.id==='play-lean'?'图标倚靠故事中触发':action?.id==='afraid'||action?.id==='angry'?'极低频插入清醒待机':action?.idle_automatic?'参与随机待机':action?.idle_state==='stand'&&action.id==='blink'?'默认待机自带眨眼':'可手动播放'}</small></p>
      <div className="action-canvas-stage"><canvas ref={canvas} width={256} height={256} aria-label={action?.name+'动画预览'}/><span>本地预览 · 不影响桌面宠物</span></div>
      {action?.physics_only&&<p className="note">此处预览物理动作。桌面上的动作由抛出、碰撞自动触发。</p>}
      {error&&<p role="alert" className="save-error">{error}</p>}
      <div className="action-transport"><button className="icon-button bordered" aria-label={playing?'暂停预览':'播放预览'} onClick={togglePlay}>{playing?<Pause size={18}/>:<Play size={18}/>}</button><button className="icon-button bordered" aria-label="从头播放" onClick={reset}><RotateCcw size={17}/></button><span>{frame+1} / {action?.frames||0} 帧</span><select aria-label="播放速度" value={speed} onChange={e=>setSpeed(Number(e.target.value))}>{[.25,.5,1,1.5,2].map(value=><option key={value} value={value}>{value}×</option>)}</select></div>
      <input className="action-scrubber" type="range" aria-label="逐帧查看" min={0} max={Math.max(0,(action?.frames||1)-1)} value={frame} onChange={e=>scrub(Number(e.target.value))}/>
      <label className="action-loop"><input type="checkbox" checked={loop} onChange={e=>setLoop(e.target.checked)}/>循环播放</label>
      <details className="action-material"><summary>素材信息 · {totalSeconds.toFixed(2)} 秒</summary><p className="muted">{action?.tempo_profile&&<>节奏：{action.tempo_profile}（1× 为推荐速度）。<br/></>}{action?.origin==='generated'?'参考原图新生成':'已有素材转换'} · {action?.review}</p></details>
      <div className="action-desktop"><button className="button primary" disabled={disabled||!visible||!action||pending||demo||action?.physics_only} onClick={()=>void desktop()}><Monitor size={16}/>在桌面播放</button><button className="button secondary" disabled={disabled||pending||demo} onClick={()=>void desktop(true)}><Square size={15}/>恢复待机</button></div>
      <p className="action-help">{demo?'界面预览模式不控制真实宠物。':!visible?'请先在“总览”显示 yuki。':action?.idle_state==='sleep'?'这里播放睡眠动作素材；持续睡眠与唤醒仍由作息系统控制。':'手动动作不会改动安静模式、移动偏好或默认呼吸待机。'}</p>
    </section>
    <ActionBrowser selected={selected} onSelect={select}/>
  </div>;
}
