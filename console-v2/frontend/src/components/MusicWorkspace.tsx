import type { MusicState } from '../bridge';
import { Toggle } from './SettingControls';
import { AudioLines, Headphones, ShieldCheck } from './Icons';
import type {WorkbenchLyric} from '../lyricPool';

export function MusicWorkspace({music,enabled,disabled,pending,onChange,lyric}:{music?:MusicState;enabled:boolean;disabled:boolean;pending:boolean;onChange:(value:boolean)=>void;lyric:WorkbenchLyric}) {
  const live=!!music?.listening;
  const level=live?Math.max(0,Math.min(1,music?.level||0)):0;
  const caption=!enabled?'声音互动已关闭':music?.suspended?(music.suspend_reason||'安静休息，暂不聆听'):!music?'连接桌宠后开始聆听':music.error?'等待播放设备':live?(music.reaction||music.label):'正在连接播放设备';
  return <div className="page-enter music-live">
    <section className="card music-listening">
      <div className="card-heading"><span className="eyebrow">{lyric.text}</span><small className="poem-source">{lyric.artist} · {lyric.song} · {lyric.album} · {lyric.year}</small><span className="subtle-badge">{live?'本机播放声音':'未监听'}</span></div>
      <div className="music-heading"><AudioLines size={26}/><h2>让日常，有一点共鸣。</h2></div>
      <p className="muted">节拍渐渐清晰，她会放下手边的小事；跳累了歇一会儿，再继续。</p>
      <div className="playback-envelope" role="meter" aria-label="系统播放音量" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(level*100)}>
        {Array.from({length:51},(_,i)=>{
          const band=live?(music?.bands[Math.min(2,Math.floor(i/17))]||0):0;
          const envelope=Math.sin((i+1)/52*Math.PI);
          return <i key={i} style={{height:`${3+Math.min(1,level*.65+band*.8)*envelope*97}%`}}/>;
        })}
      </div>
      <div className="playback-caption"><span>{caption}</span><span>音量 {Math.round(level*100)}%</span></div>
      <Toggle label="随声音互动" description="跟随音乐起舞，累了短暂休息；安静模式下暂停" checked={enabled} disabled={disabled} pending={pending} onChange={onChange}/>
    </section>
    <section className="music-observations" aria-label="声音互动状态">
      <div><span className="section-label"><Headphones size={15}/>播放来源</span><strong>{live?music?.source:'系统默认播放设备'}</strong><p>捕获电脑播放的声音，不使用麦克风。</p></div>
      <div><span className="section-label">此刻的节奏</span><strong className="music-tempo">{live&&music?.bpm?`${music.bpm} BPM`:'—'}<small>{live&&music?.bpm?'估计节拍':'等待稳定的节拍'}</small></strong><p>每次跳舞约 30–50 秒，休息 12–20 秒后继续。</p></div>
      <div><span className="section-label">她的回应</span><strong>{music?.reaction||'听一听，也歇一歇'}</strong><p>拖动、聊天、停靠与夜间休息优先。</p></div>
    </section>
    {enabled&&music?.error&&<p className="note" role="status">{music.error}</p>}
    <p className="page-note"><ShieldCheck size={16}/>仅在本机估计音量与节奏，不保存录音，不识别歌曲或语音内容。</p>
  </div>;
}

