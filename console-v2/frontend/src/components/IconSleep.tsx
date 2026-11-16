import { useEffect, useState } from 'react';
import { Folder, File, Moon, RefreshCw, Sun, LoaderCircle } from './Icons';
import { demo, type EdgeOptions, type IconSleepOptions, type PetSnapshot } from '../bridge';
import { Range, Toggle } from './SettingControls';
import './IconSleep.css';

type Props={state:PetSnapshot|null;disabled:boolean;act:(name:string,payload?:Record<string,unknown>,success?:string)=>Promise<boolean>};
const fallback:IconSleepOptions={direction:'auto',offset_x:0,offset_y:0,breath:55,duration:0,snap_distance:100};
const poses=[['sit-front','转头坐坐'],['sit-back','回眸坐坐'],['prone-front','托腮趴趴'],['prone-back','回头趴趴'],['perch-front','朝你斜坐'],['perch-back','侧背倚靠']];
const edgeFallback:EdgeOptions={enabled:false,windows:true,screens:true,corner:'right',delay:8};
export function IconSleep({state,disabled,act}:Props){
  const sleep=state?.icon_sleep,options=sleep?.options??fallback;
  const [selected,setSelected]=useState(''),[query,setQuery]=useState(''),[busy,setBusy]=useState(false);
  const icons=sleep?.icons??[],active=!!sleep?.target_id;
  useEffect(()=>{if(!disabled&&!demo)void act('refresh_desktop_icons');},[disabled]);
  useEffect(()=>{if(icons.length&&!icons.some(i=>i.id===selected))setSelected((icons.find(i=>i.available!==false)??icons[0]).id);},[icons,selected]);
  const configure=(key:keyof IconSleepOptions,value:IconSleepOptions[keyof IconSleepOptions])=>act('configure_icon_sleep',{[key]:value});
  const edge=state?.edge_attachment,edgeOptions=edge?.options??edgeFallback;
  const configureEdge=(key:keyof EdgeOptions,value:EdgeOptions[keyof EdgeOptions])=>act('configure_edge_attachment',{[key]:value});
  const filtered=icons.filter(i=>i.name.toLowerCase().includes(query.toLowerCase()));
  const invoke=async(name:string,payload:Record<string,unknown>={})=>{setBusy(true);try{await act(name,payload);}finally{setBusy(false);}};
  const locked=disabled||busy||demo;
  return <div className="icon-sleep-page page-enter">
    <section className="sleep-targets">
      <div className="sleep-section-heading"><h2>桌面图标</h2><button className="icon-button bordered" title="重新扫描桌面快捷方式和图标文件，更新下面可供雪依靠的目标。" aria-label="刷新桌面图标" disabled={locked||sleep?.scanning} onClick={()=>void invoke('refresh_desktop_icons')}>{sleep?.scanning?<LoaderCircle size={17} className="spin"/>:<RefreshCw size={17}/>}</button></div>
      <input className="sleep-search" aria-label="搜索桌面图标" placeholder="搜索名称" value={query} onChange={e=>setQuery(e.target.value)}/>
      {demo&&<p className="muted">预览模式未连接 Windows 桌面。</p>}
      {sleep?.error&&<p role="alert" className="save-error">{sleep.error}</p>}
      <div className="sleep-icon-list" role="group" aria-label="选择依靠图标">{filtered.map(icon=><button key={icon.id} className={`sleep-icon-row ${selected===icon.id?'selected':''}`} aria-pressed={selected===icon.id} onClick={()=>setSelected(icon.id)}>{icon.folder?<Folder size={19}/>:<File size={19}/>}<span>{icon.name}</span>{sleep?.target_id===icon.id&&<Moon size={15}/>}</button>)}</div>
      {!filtered.length&&!sleep?.scanning&&<p className="muted">{icons.length?'没有匹配的图标。':'尚未读取到桌面图标。'}</p>}
      {icons.find(i=>i.id===selected)?.available===false&&<p className="muted">附近空间不足，可缩小宠物、调整方向或选择其他图标。</p>}
      <div className="sleep-status" role="status"><Moon size={17}/><span>{sleep?.message||'选一个图标，让她坐坐或趴一会儿'}</span></div>
      <div className="sleep-commands"><button className="button primary" disabled={locked||!state?.visible||!selected||sleep?.scanning} onClick={()=>void invoke('start_icon_sleep',{icon_id:selected})}><Moon size={16}/>去这里休息</button><button className="button secondary" disabled={locked||!active} onClick={()=>void invoke('stop_icon_sleep')}><Sun size={16}/>离开图标</button></div>
    </section>
    <section className="sleep-options">
      <h2>依靠偏好</h2>
      <div className="pose-gallery" role="group" aria-label="选择自然姿态">{poses.map(([id,label])=><button key={id} className={options.direction===id?'pose-card selected':'pose-card'} aria-pressed={options.direction===id} disabled={locked} onClick={()=>void configure('direction',id)}><img src={`/interaction-previews/${id}.png`} alt=""/><span>{label}</span></button>)}</div>
      <label className="setting-label" htmlFor="sleep-direction">自然姿态</label><select id="sleep-direction" value={options.direction} disabled={locked} onChange={e=>void configure('direction',e.target.value)}><option value="auto">自动选择</option>{poses.map(([id,label])=><option key={id} value={id}>{label}</option>)}<option value="left">左侧背靠</option><option value="right">右侧背靠</option><option value="back">背对屏幕</option><option value="front">正面背靠</option></select>
      <p className="muted">仅依靠的目标图标能遮挡裙摆，头发始终在图标上方。其他图标和所有文字都不裁切宠物；靠近屏幕边缘时自动换姿势或轻微内移。</p>
      <Range label="水平偏移" description="" value={options.offset_x} min={-100} max={100} unit=" px" defaultValue={0} disabled={locked} onCommit={v=>configure('offset_x',v)}/>
      <Range label="垂直偏移" description="" value={options.offset_y} min={-100} max={100} unit=" px" defaultValue={0} disabled={locked} onCommit={v=>configure('offset_y',v)}/>
      <Range label="呼吸强度" description="" value={options.breath} min={0} max={100} unit="%" defaultValue={55} disabled={locked} onCommit={v=>configure('breath',v)}/>
      <Range label="睡眠时长" description="0 分钟表示持续睡眠" value={options.duration} min={0} max={120} unit=" 分钟" defaultValue={0} disabled={locked} onCommit={v=>configure('duration',v)}/>
      <Toggle label="拖放即时吸附" description="拖到图标、窗口或屏幕边沿，松手立即停靠；暂停走动时也可用" checked={state?.preferences.auto_snap??true} disabled={locked} onChange={v=>act('set_preference',{key:'auto_snap',value:v})}/>
      <Range label="自动依靠距离" description="" value={options.snap_distance} min={30} max={240} unit=" px" defaultValue={100} disabled={locked||!state?.preferences.auto_snap} onCommit={v=>configure('snap_distance',v)}/>
    </section>
    <section className="edge-options sleep-options">
      <h2>自然停靠</h2>
      <p className="muted">手动拖到边框附近并松手时停靠：侧边抓框爬行，下沿悬挂轻晃，上沿坐着或趴着。开启“自主窗口互动”后，她也会偶尔走近可见窗口侧边，或跳上前台窗口上沿；停靠后跟随窗口移动与缩放，平时仍以日常待机为主。</p>
      <Toggle label="停靠应用与浏览器窗口" description="关闭后手动与自主行为都不再选择窗口侧边或上沿；屏幕边缘由下一项单独控制" checked={edgeOptions.windows} disabled={locked} onChange={v=>{void configureEdge('windows',v);}}/>
      <Toggle label="允许拖到屏幕边缘停靠" checked={edgeOptions.screens} disabled={locked} onChange={v=>{void configureEdge('screens',v);}}/>
      <label className="setting-label" htmlFor="edge-corner">角落等距时偏好</label><select id="edge-corner" value={edgeOptions.corner} disabled={locked} onChange={e=>void configureEdge('corner',e.target.value as 'left'|'right')}><option value="right">右侧</option><option value="left">左侧</option></select>
      <div role="status" className="sleep-status"><span>{edge?.active?edge.message:'等待手动拖放或自主停靠'}</span></div>
      {edge?.error&&<p role="alert" className="save-error">{edge.error}</p>}
      <button className="button secondary" disabled={locked||!edge?.active} onClick={()=>void invoke('stop_edge_attachment')}>离开边缘</button>
      <p className="muted">图标互动优先。跟随浏览器外框，不跟随网页内部卡片；若要覆盖在窗口上方，请开启「始终置顶」。</p>
    </section>
  </div>;
}
