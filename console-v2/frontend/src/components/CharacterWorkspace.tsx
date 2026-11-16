import {useEffect,useRef,useState} from 'react';
import {SortableGroup} from './SortableGroup';
import {ChevronRight} from 'lucide-react';
import type {usePetController} from '../usePetController';
import {defaults} from '../bridge';
import {host} from '../host';
import {formatTime, type Workbench} from '../useWorkbench';
import {MusicWorkspace} from './MusicWorkspace';
import type {WorkbenchLyric} from '../lyricPool';
import {ActionLibrary} from './ActionLibrary';
import {CharacterPreview} from './CharacterPreview';
import {Range,Toggle} from './SettingControls';
import {IconSleep} from './IconSleep';
import {BubbleSettings} from './WorkbenchSettings';
import catalog from '../../public/actions/catalog.json';
export function CharacterWorkspace({tab,pet,work,reduced,lyric}:{tab:number;pet:ReturnType<typeof usePetController>;work:Workbench;reduced:boolean;lyric:WorkbenchLyric}){
 const pref=pet.state?.preferences??defaults,disabled=!pet.connected||pet.connecting;
 const [confirmClear,setConfirmClear]=useState(false);
 const focus=pet.state?.focus,memory=pet.state?.memory,perch=pet.state?.window_perch,activity=pet.state?.activity;
 const appearanceCommand=useRef(pet.act),previewState=useRef<boolean|null>(null);
 appearanceCommand.current=pet.act;
 useEffect(()=>{
  if(tab!==2||!pet.connected||host?.kind!=='electron'){
   if(previewState.current===true){previewState.current=false;void appearanceCommand.current('set_appearance_preview',{enabled:false});}
   return;
  }
  const syncPreview=()=>{
   const enabled=document.visibilityState==='visible'&&document.hasFocus();
   if(previewState.current===enabled)return;
   previewState.current=enabled;
   void appearanceCommand.current('set_appearance_preview',{enabled}).then(ok=>{if(!ok&&previewState.current===enabled)previewState.current=null;});
  };
  syncPreview();window.addEventListener('focus',syncPreview);window.addEventListener('blur',syncPreview);document.addEventListener('visibilitychange',syncPreview);
  return()=>{window.removeEventListener('focus',syncPreview);window.removeEventListener('blur',syncPreview);document.removeEventListener('visibilitychange',syncPreview);if(previewState.current!==false){previewState.current=false;void appearanceCommand.current('set_appearance_preview',{enabled:false});}};
 },[tab,pet.connected]);
 const desktopConnected=!disabled&&host?.kind==='electron';
 const previewLive=desktopConnected&&(!!pet.state?.visible||activity?.key==='leaving');
 const toggle=(key:'quiet'|'auto_snap'|'always_on_top'|'random_movement'|'autonomous_play'|'autonomous_icons'|'autonomous_speech'|'paused'|'greeting'|'focus_companion'|'focus_click_through'|'autonomous_windows'|'relationship_memory',label:string,description:string,locked=false)=><Toggle key={key} label={label} description={description} checked={pref[key]} disabled={disabled||locked} pending={pet.pending.includes('preference:'+key)} onChange={v=>void pet.setPreference(key,v)}/>;
 return <div className="subpage-motion" key={tab}>
 {tab===0&&<><MusicWorkspace music={pet.state?.music} enabled={pref.music_reactions} disabled={disabled} pending={pet.pending.includes('preference:music_reactions')} onChange={v=>void pet.setPreference('music_reactions',v)} lyric={lyric}/></>}
 {tab===1&&<><ActionLibrary reduced={reduced} disabled={disabled} visible={pet.state?.visible??false} act={pet.act}/><details className="content-section"><summary>系统动作与渲染方式</summary><div className="system-actions">{[['出现与离开','显示／隐藏宠物时自动执行，不在预览中退出程序。'],['拖拽与抛出','鼠标拖放与释放速度触发，沿用已有动作和物理。'],['碰撞与攀附','四边接触时短暂反应，满足条件时攀附窗口。'],['单击与摸头','单击按头部、身体、脚区分回应；长按头部摸头，双击害羞；连续点击保留果冻弹性。']].map(([a,b])=><div key={a}><h3>{a}</h3><p>{b}</p></div>)}</div><p className="muted">当前使用 PNG 帧动画与程序微动；Live2D 尚未配置。共有 {catalog.length} 组登记素材。</p></details></>}
 {tab===2&&<div className="two-column appearance-page"><section className="content-section appearance-preview"><CharacterPreview live={previewLive} hidden={desktopConnected&&!previewLive&&pet.state?.visible===false} opacity={pref.opacity/100} scale={Math.min(1.2,Math.max(.65,pref.size/100))}/></section><div><section className="content-section"><h2>角色外观</h2><SortableGroup scope="appearance-entries"><Range key="size" label="宠物大小" description="等比调整显示大小" value={pref.size} min={50} max={200} unit="%" defaultValue={defaults.size} disabled={disabled} pending={pet.pending.includes('preference:size')} onCommit={v=>pet.setPreference('size',v)}/><Range key="opacity" label="不透明度" description="调整桌宠透明度" value={pref.opacity} min={30} max={100} unit="%" defaultValue={defaults.opacity} disabled={disabled} pending={pet.pending.includes('preference:opacity')} onCommit={v=>pet.setPreference('opacity',v)}/>{toggle('always_on_top','始终置顶','显示在普通窗口上方')}</SortableGroup></section><BubbleSettings/></div></div>}
 {tab===3&&<><div className="behavior-now"><div><small>现在</small><h2>{activity?.label||pet.state?.status||'等待连接'}</h2><p>{activity?.detail||'此刻没有额外动作'}</p><p className="muted">当前目标：{pet.state?.patrol?.target||'尚未选择'}</p></div><ChevronRight size={20}/><div><small>接下来</small><h3>{pet.state?.sleep?.scheduled?'按睡眠日程休息':pet.state?.patrol?.next_intent||'由生活系统自然选择'}</h3></div><ChevronRight size={20}/><div><small>为什么</small><h3>{pref.quiet?'安静模式':pet.state?.sleep?.sleeping?'睡眠时段':pet.state?.edge_attachment?.active?'窗口附着':'日常陪伴'}</h3><p>{pet.state?.patrol?.reason||pet.state?.routine?.name||'以待机为主，少量散步'}</p></div></div><SortableGroup scope="behavior-panels" className="two-column"><section key="movement" className="content-section"><h2>陪伴与移动</h2><p className="muted movement-hint">空闲时会低频走动、观察附近图标或窗口；活动、睡眠、安静与用户操作期间会暂停。</p><SortableGroup scope="behavior-entries">{toggle('random_movement','自主走动','允许在安全的桌面区域移动',pref.quiet)}{toggle('autonomous_play','自主玩耍','空闲时探索、阅读或休息',pref.quiet)}{toggle('autonomous_icons','自主图标互动','自主观察、依靠和攀坐图标',pref.quiet)}{toggle('autonomous_windows','自主窗口互动','空闲时攀爬窗口边框或停靠上沿',pref.quiet)}{toggle('autonomous_speech','自主短句','偶尔分享一句，至少间隔三分钟',pref.quiet)}{toggle('paused','暂停走动','保留呼吸、拖动与手动动作',pref.quiet)}{toggle('quiet','安静模式','减少主动打扰与移动',!!work.focus.end)}{toggle('greeting','问候气泡','点击时显示问候',pref.quiet)}<Range key="speed" label="移动速度" description="调整桌面移动速度" value={pref.speed} min={10} max={150} unit=" px/s" defaultValue={defaults.speed} disabled={disabled} onCommit={v=>pet.setPreference('speed',v)}/><div key="activity" className="segmented">{['少动','默认','活跃'].map(v=><button key={v} className={pref.activity===v?'selected':''} aria-pressed={pref.activity===v} disabled={disabled||pref.quiet} onClick={()=>void pet.setPreference('activity',v)}>{v}</button>)}</div></SortableGroup></section><section key="rules" className="content-section"><h2>生活规则</h2><dl className="rules-list"><div><dt>四种待机</dt><dd>站立、坐下、趴着、睡眠；由状态机与素材条件选择。</dd></div><div><dt>睡眠</dt><dd>00:00–07:00、13:00–14:00；点击、拖拽、消息与较大声音可唤醒，安静 2 分钟重新入睡。</dd></div><div><dt>附着</dt><dd>手拖至边框或图标即时吸附；自主时会走近可见窗口侧边攀爬，或跳上前台窗口上沿并跟随窗口移动。</dd></div><div><dt>专注陪伴</dt><dd>专注时坐下陪伴并临时安静；可选用鼠标穿透，休息或结束自动恢复。</dd></div><div><dt>动作优先级</dt><dd>拖拽与物理、睡眠过渡、手动动作优先，音乐与日常不抢占。</dd></div></dl></section><section key="focus-window" className="content-section"><h2>专注与窗口</h2><SortableGroup scope="focus-entries">{toggle('focus_companion','专注陪伴','专注时坐下并临时安静')}{toggle('focus_click_through','专注时鼠标穿透','专注阶段暂时忽略鼠标，休息或结束后自动恢复',!pref.focus_companion)}</SortableGroup><p className="muted">{focus?.active?(focus.phase==='break'?'正在陪你休息':'正在安静专注')+(focus.remaining?` · 还剩 ${formatTime(focus.remaining)}`:''):'启动专注计时后生效。'}</p><div className="inline-actions"><button className="button secondary" disabled={disabled||pref.quiet||pref.paused||!!focus?.active} onClick={()=>void pet.act('perch_window',{},'去前台窗口上沿坐一会儿')}>去窗口坐坐</button>{perch?.active&&<button className="button secondary" disabled={disabled} onClick={()=>void pet.act('stop_window_perch',{},'已离开窗口')}>离开窗口</button>}<span className="muted">{perch?.error||perch?.message}</span></div></section><section key="memory" className="content-section"><h2>关系记忆</h2>{toggle('relationship_memory','记录相伴计数','只写入点击、摸头、专注分钟和日期；不保存聊天、按键、窗口标题或文件内容')}<dl className="rules-list"><div><dt>相伴</dt><dd>{memory?.days_together??0} 天 · 点击 {memory?.clicks??0} 次 · 摸头 {memory?.headpats??0} 次</dd></div><div><dt>专注与问候</dt><dd>{memory?.focus_minutes??0} 分钟 · 问候 {memory?.greetings??0} 次</dd></div></dl><p className="muted">{memory?.error||'数据只保存在本机设置文件旁。关闭开关后停止记录，已有计数仍可查看或清除。'}</p><div className="inline-actions"><button className="button secondary" disabled={disabled} onClick={()=>{if(!confirmClear){setConfirmClear(true);return;}setConfirmClear(false);void pet.act('reset_companion_memory',{},'关系记忆已清除');}}>{confirmClear?'再点一次确认清除':'清除记录'}</button>{confirmClear&&<span className="muted">只清除计数与日期，不涉及任何内容。</span>}</div></section></SortableGroup><details className="content-section"><summary>图标互动与窗口停靠的详细设置</summary><IconSleep state={pet.state} disabled={disabled} act={pet.act}/></details></>}
 </div>;
}
