import {useEffect,useRef,useState} from 'react';
import {Music2,Pause,Play,SkipBack,SkipForward,Download,Search} from 'lucide-react';
import type {Workbench} from '../useWorkbench';
import {formatTime} from '../useWorkbench';
import type {WorkbenchLyric} from '../lyricPool';
import {useNow} from '../useNow';
import {mediaPosition,lyricIndex} from '../mediaPlayback';
import {Toggle,Range} from './SettingControls';
import type {LyricsSettings} from '../host/types';

export function MusicPlayer({work,lyric}:{work:Workbench;lyric:WorkbenchLyric}){
 const m=work.data.media,l=work.data.lyrics,s=l?.settings,now=useNow();
 const playing=m.status==='Playing',command=playing?'pause':'play',key=[m.app,m.title,m.artist].join('\n');
 const position=mediaPosition(m,now),duration=m.duration||0,start=m.start||0;
 const timeline=Number.isFinite(m.position)&&duration>start;
 const [draft,setDraft]=useState<number|null>(null),[feedback,setFeedback]=useState('');
 const edited=useRef<{position:number;key:string}|null>(null);
 useEffect(()=>{edited.current=null;setDraft(null);setFeedback('');},[key]);
 const enabled=(name:'previous'|'next'|'play'|'pause'|'seek')=>work.supported&&m.available&&!!m.app&&!!m.controls?.[name]&&!work.busy;
 const control=async(name:'previous'|'next'|'play'|'pause')=>{setFeedback('');if(await work.action('media-control',{command:name,app:m.app}))setFeedback('已发送'+({previous:'上一首',next:'下一首',play:'播放',pause:'暂停'}[name])+'指令');};
 const seek=async()=>{const edit=edited.current;edited.current=null;if(!edit||edit.key!==key){setDraft(null);return;}try{if(await work.action('media-control',{command:'seek',app:m.app,title:m.title||'',artist:m.artist||'',position:edit.position}))setFeedback('已调整播放进度');}finally{setDraft(null);}};
 const set=(patch:Partial<LyricsSettings>)=>{void work.action('lyrics-settings',patch);};
 const index=l?.timed?lyricIndex(l.lines,position-start):-1;
 return <div className="media-v2">
  <div className="media-title"><Music2 size={22}/><div><h3>{m.available?m.title||'无标题音轨':'等待一首歌'}</h3><p className={m.available?undefined:'lyric-quote'}>{m.available?m.artist||m.app||'系统媒体播放器':lyric.text}</p>{!m.available&&<small>{lyric.artist} · {lyric.song}</small>}</div><span className={'equalizer '+(playing?'playing':'')} aria-label={m.status||'未播放'}>{[0,1,2,3].map(i=><i key={i}/>)}</span></div>
  <input className="media-seek" type="range" aria-label="音乐播放进度" aria-valuetext={formatTime((draft??position)-start)+' / '+formatTime(duration-start)} min={start} max={Math.max(start+1,duration)} step={0.1} value={draft??position} disabled={!enabled('seek')||duration<=start} onChange={e=>{const value=Number(e.target.value);edited.current={position:value,key};setDraft(value);}} onPointerUp={()=>void seek()} onPointerCancel={()=>{edited.current=null;setDraft(null);}} onKeyUp={e=>{if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','Home','End','PageUp','PageDown'].includes(e.key))void seek();}} onBlur={()=>void seek()}/>
  <div className="media-times"><span>{timeline?formatTime((draft??position)-start):'—:—'}</span><span>{draft!==null?'调整进度':playing?'播放中':m.status==='Paused'?'已暂停':m.available?'已识别歌曲':'暂无播放'}</span><span>{timeline?formatTime(Math.max(0,duration-start)):'—:—'}</span></div>
  <div className="media-controls" role="group" aria-label="后台音乐控制" aria-busy={work.busy==='media-control'}>
   <button className="icon-button bordered" aria-label="上一首" title="上一首" disabled={!enabled('previous')} onClick={()=>void control('previous')}><SkipBack size={17}/></button>
   <button className="button secondary media-play" aria-label={playing?'暂停音乐':'播放音乐'} disabled={!enabled(command)} onClick={()=>void control(command)}>{playing?<Pause size={16}/>:<Play size={16}/>} {playing?'暂停':'播放'}</button>
   <button className="icon-button bordered" aria-label="下一首" title="下一首" disabled={!enabled('next')} onClick={()=>void control('next')}><SkipForward size={17}/></button>
  </div>
  <p className="muted media-feedback" role="status">{work.busy==='media-control'?'正在等待播放器响应…':!work.supported?'请在 Windows 工作台中控制音乐。':!m.available?'先在音乐播放器中打开一首歌。':feedback||(m.app?.startsWith('netease-uia:')&&m.status==='Unknown'?'已识别网易云歌曲；该版本暂未提供可读取的播放状态和进度。':!m.controls?.seek?'当前播放器不支持拖动进度。':'支持拖动进度，或用方向键微调。')}</p>
  <div className="lyrics-section">
   <div className="lyrics-heading"><h3>当前歌词</h3>{s&&<Toggle label="显示歌词" description="工作台与桌面歌词总开关" checked={s.enabled} disabled={!!work.busy} onChange={enabled=>set({enabled})}/>}</div>
   {(!s||s.enabled)&&<>
    {l?.lines.length?<div className={'lyrics-preview lyrics-palette-'+s?.palette+' lyrics-style-'+s?.style} style={{opacity:(s?.opacity??100)/100}}>
     {l.timed?<><p className="lyric-quote current-lyric">{index>=0?l.lines[index].text||'♪':'♪ 等待歌词开始'}</p><p className="lyric-quote next-lyric">{l.lines[index+1]?.text||'♪'}</p></>:<div className="plain-lyrics">{l.lines.map((line,i)=><p className="lyric-quote" key={i}>{line.text}</p>)}</div>}
    </div>:<p className="muted lyrics-empty">{l?.busy?'正在查找歌词…':'暂无当前歌曲歌词，可联网查找或导入 LRC／TXT。'}</p>}
    {l?.error&&<p className="muted" role="status">{l.error}</p>}
    {l?.source&&<p className="muted lyrics-source">{l.source} · {l.timed?'随播放同步':'纯文本，无时间轴'}</p>}
    <div className="inline-actions lyrics-actions"><button className="button secondary" disabled={!work.supported||!m.title||!!work.busy||l?.busy} onClick={()=>void work.action('lyrics-find')}><Search size={14}/>联网查找歌词</button><button className="button secondary" disabled={!work.supported||!m.title||!!work.busy||l?.busy} onClick={()=>void work.action('lyrics-import')}><Download size={14}/>导入歌词</button></div>
    <p className="muted lyrics-network-note">查找时将当前曲名、歌手和时长发送至 LRCLIB；不上传音频。</p>
   </>}
   {s&&<details className="lyrics-options"><summary>歌词外观与桌面浮窗</summary><div className="lyrics-options-body">
    <Toggle label="自动查找歌词" description="切歌后将曲名、歌手和时长发送至 LRCLIB；优先使用已缓存歌词" checked={s.autoFind} disabled={!!work.busy} onChange={autoFind=>set({autoFind})}/>
    <fieldset disabled={!!work.busy}><legend>歌词颜色</legend><div className="lyrics-palettes">{([['ice','冰蓝'],['white','月白'],['rose','浅樱'],['gold','暖金']] as const).map(([value,label])=><button key={value} className={'lyrics-swatch swatch-'+value} aria-pressed={s.palette===value} onClick={()=>set({palette:value})}>{label}</button>)}</div></fieldset>
    <label className="compact-field">歌词款式<select aria-label="歌词款式" value={s.style} disabled={!!work.busy} onChange={e=>set({style:e.target.value as LyricsSettings['style']})}><option value="glass">柔和底板</option><option value="plain">纯文字</option><option value="outline">描边文字</option></select></label>
    <Range label="歌词不透明度" description="20% 更通透，100% 完全显示；同时应用于工作台和桌面歌词" value={s.opacity} min={20} max={100} unit="%" disabled={!!work.busy} pending={work.busy==='lyrics-settings'} defaultValue={90} onCommit={opacity=>work.action('lyrics-settings',{opacity})}/>
    <Toggle label="桌面悬浮歌词" description="拖动浮窗顶部可移动；关闭按钮可隐藏" checked={s.overlay} disabled={!!work.busy||!s.enabled} onChange={overlay=>set({overlay})}/>
    <Toggle label="始终置顶" description="让歌词浮窗显示在其他应用窗口上方" checked={s.alwaysOnTop} disabled={!!work.busy} onChange={alwaysOnTop=>set({alwaysOnTop})}/>
   </div></details>}
  </div>
 </div>;
}
