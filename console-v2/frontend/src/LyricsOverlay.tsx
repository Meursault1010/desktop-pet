import {useEffect,useState} from 'react';
import {createRoot} from 'react-dom/client';
import type {DesktopSnapshot,LyricsSnapshot} from './host/types';
import {mediaPosition,lyricIndex} from './mediaPlayback';
import './lyrics.css';
type State=LyricsSnapshot&{media:DesktopSnapshot['media']};
declare global {interface Window {yukiLyrics?:{snapshot:()=>Promise<State>;hide:()=>Promise<void>;subscribe:(listener:(state:State)=>void)=>()=>void}}}
function Overlay(){
 const [state,setState]=useState<State|null>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;const host=window.yukiLyrics;const off=host?.subscribe(s=>{if(active)setState(s);});void host?.snapshot().then(s=>{if(active)setState(s);}).catch(()=>{if(active)setError('歌词状态读取失败');});return()=>{active=false;off?.();};},[]);
 if(!state)return <p className="overlay-empty">{error||'正在连接歌词…'}</p>;
 const {settings:s,media:m,lines}=state,index=state.timed?lyricIndex(lines,mediaPosition(m,Date.now())-(m.start||0)):-1;
 const text=!m.available?'在播放器中打开一首歌':!lines.length?'请在工作台查找或导入当前歌曲歌词':state.timed?(index<0?'♪ 等待歌词开始':lines[index].text||'♪'):lines[0]?.text;
 return <main className={'lyrics-overlay lyrics-palette-'+s.palette+' lyrics-style-'+s.style}>
  <header className="overlay-drag"><span>{m.title||'Yuki · 桌面歌词'}{m.artist?' · '+m.artist:''}</span><button aria-label="隐藏桌面歌词" title="隐藏桌面歌词" onClick={()=>void window.yukiLyrics?.hide().catch(()=>setError('隐藏失败，请在工作台关闭'))}>×</button></header>
  <p className="overlay-current">{text}</p><p className="overlay-next">{error||(state.timed?lines[index+1]?.text:lines.length?'纯文本歌词 · 完整内容见工作台':'支持 LRC 同步歌词与 TXT 歌词')}</p>
 </main>;
}
createRoot(document.getElementById('root')!).render(<Overlay/>);
