import {useEffect,useRef,useState} from 'react';
import {AssistantWorkspace} from './AssistantWorkspace';
import {AudioLines,Check,Clock3,Code2,FileText,Moon,RefreshCw,Sun,Trash2} from './Icons';
import {host} from '../host';
import type {DesktopSnapshot} from '../host/types';
import type {PetSnapshot} from '../bridge';
import '../desktop.css';

const empty:DesktopSnapshot={clipboard:[],clipboardPaused:false,media:{available:false},battery:{available:false},events:[],weather:null,city:'',inbox:''};
const time=(at:number)=>new Date(at).toLocaleTimeString('zh-CN',{hour:'2-digit',minute:'2-digit'});
function weatherName(code?:number){if(code===undefined)return '等待天气';if(code===0)return '晴';if(code<=3)return '多云';if(code<=48)return '雾';if(code<=67)return '雨';if(code<=77)return '雪';if(code<=82)return '阵雨';if(code<=86)return '阵雪';return '雷雨';}
function duration(value=0){return `${Math.floor(Math.max(0,value)/60)}:${String(Math.floor(Math.max(0,value)%60)).padStart(2,'0')}`;}

export function FutureWorkspace({page,status,sleep}:{page:'assistant'|'tools';status:string;sleep?:PetSnapshot['sleep']}){
  if(page==='assistant')return <AssistantWorkspace/>;
  return <DesktopWorkspace status={status} sleep={sleep}/>;
}
function DesktopWorkspace({status,sleep}:{status:string;sleep?:PetSnapshot['sleep']}){
  const [data,setData]=useState(empty),[now,setNow]=useState(new Date()),[city,setCity]=useState('');
  const [error,setError]=useState(''),[busy,setBusy]=useState(''),[copied,setCopied]=useState(''),[loading,setLoading]=useState(!!host?.desktopSnapshot);
  const live=useRef(true),weatherRequested=useRef(false);
  const supported=!!host?.desktopSnapshot;
  useEffect(()=>{
    live.current=true;let inFlight=false;
    const refresh=async()=>{if(!host?.desktopSnapshot||inFlight)return;inFlight=true;try{const value=await host.desktopSnapshot();if(live.current){setData(value);setLoading(false);if(!weatherRequested.current){setCity(value.city);weatherRequested.current=true;if(value.city)void host.desktopAction?.({name:'weather',value:value.city}).then(v=>{if(live.current)setData(v);}).catch(e=>{if(live.current)setError(String(e.message||e));});}}}catch(e){if(live.current){setError(String(e instanceof Error?e.message:e));setLoading(false);}}finally{inFlight=false;}};
    void refresh();const poll=window.setInterval(()=>void refresh(),2000),clock=window.setInterval(()=>setNow(new Date()),1000);
    const unsubscribe=host?.desktopSubscribe?.(()=>void refresh());
    return()=>{live.current=false;clearInterval(poll);clearInterval(clock);unsubscribe?.();};
  },[]);
  useEffect(()=>{if(!data.city||!supported)return;const timer=setInterval(()=>{void host?.desktopAction?.({name:'weather',value:data.city}).then(v=>{if(live.current)setData(v);}).catch(e=>{if(live.current)setError(String(e.message||e));});},600000);return()=>clearInterval(timer);},[data.city,supported]);
  async function action(name:string,value?:unknown){if(!host?.desktopAction||busy)return;setBusy(name);setError('');try{const result=await host.desktopAction({name,value});if(live.current){setData(result);if(name==='clipboard-copy')setCopied(String(value));}}catch(e){if(live.current)setError(String(e instanceof Error?e.message:e));}finally{if(live.current)setBusy('');}}
  const w=data.weather,m=data.media;
  const clock=now.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
  const sleepLabel=sleep?.sleeping?'熟睡中':sleep?.phase==='waking'?'慢慢醒来':sleep?.scheduled&&sleep.resume_in>0?`${Math.ceil(sleep.resume_in/60)} 分钟后小憩`:status;
  return <div className="desktop-workspace page-enter" aria-busy={loading}>
    {!supported&&<p className="desktop-notice">浏览器中仅展示布局。请从 Electron 启动 Yuki，读取这台电脑的真实状态。</p>}
    {error&&<div className="desktop-notice desktop-error" role="alert"><span>{error}</span><button onClick={()=>setError('')}>关闭</button></div>}
    <div className="desktop-atmosphere">
      <section className="desktop-clock" aria-label="本地时钟">
        <div className="clock-face" aria-hidden="true"><svg viewBox="0 0 120 120"><circle cx="60" cy="60" r="49"/>{Array.from({length:12},(_,i)=><path key={i} d="M60 14v5" transform={`rotate(${i*30} 60 60)`}/>)}<path className="clock-hour" d="M60 60V35" transform={`rotate(${now.getHours()*30+now.getMinutes()/2} 60 60)`}/><path className="clock-minute" d="M60 60V24" transform={`rotate(${now.getMinutes()*6} 60 60)`}/><circle className="clock-pivot" cx="60" cy="60" r="2"/></svg></div>
        <div><h2>此刻的桌面</h2><time dateTime={now.toISOString()}>{clock}<span>{String(now.getSeconds()).padStart(2,'0')}</span></time><p>{now.toLocaleDateString('zh-CN',{month:'long',day:'numeric',weekday:'long'})}</p></div>
        <div className="desktop-poem"><p>“We are such stuff<br/>As dreams are made on.”</p><span>Shakespeare · The Tempest</span></div>
      </section>
      <section className="desktop-weather" aria-labelledby="weather-heading"><div className="desktop-section-heading"><h2 id="weather-heading">窗外</h2><Sun size={19}/></div>
        {w?<><div className="weather-reading"><strong>{Math.round(w.temperature_2m??0)}<span>°</span></strong><div><p>{w.city} · {weatherName(w.weather_code)}</p><span>{Math.round(w.low??0)}° / {Math.round(w.high??0)}°</span></div></div><p className="weather-detail">体感 {w.apparent_temperature??'—'}° · 湿度 {w.relative_humidity_2m??'—'}% · 风速 {w.wind_speed_10m??'—'} km/h</p></>:<p className="desktop-empty">设定一座城市，让雪知道窗外的天气。</p>}
        <form className="weather-search" onSubmit={e=>{e.preventDefault();void action('weather',city.trim());}}><input aria-label="天气城市" value={city} maxLength={80} onChange={e=>setCity(e.target.value)} placeholder="城市名称 / 拼音"/><button className="icon-button" disabled={!supported||!!busy||!city.trim()} aria-label="获取天气"><RefreshCw size={16} className={busy==='weather'?'spin':''}/></button></form>
        <span className="weather-credit">Open-Meteo · {w?`${time(w.at)} 更新`:'按城市查询，无需定位'}</span>
      </section>
    </div>
    <div className="desktop-life-strip"><Moon size={17}/><strong>雪 · {sleepLabel}</strong><span>睡眠 00:00–07:00 / 13:00–14:00</span><span>{data.battery.available?`电量 ${data.battery.percent??'—'}%`:'交流电 / 无电池信息'}{data.drives?.length?` · U 盘 ${data.drives.join('、')}`:''}</span></div>
    <div className="desktop-columns"><div className="desktop-main-column">
      <section className="desktop-panel clipboard-panel"><div className="desktop-section-heading"><h2><FileText size={18}/>剪切板<span className="desktop-count">{data.clipboard.length} / 10</span></h2><div><button className="text-link" disabled={!supported||!!busy} onClick={()=>void action('clipboard-pause',!data.clipboardPaused)}>{data.clipboardPaused?'继续记录':'暂停记录'}</button><button className="icon-button" aria-label="清空剪切板记录" title="清空记录" disabled={!supported||!!busy||!data.clipboard.length} onClick={()=>void action('clipboard-clear')}><Trash2 size={16}/></button></div></div>
        <p className="desktop-caption">{data.clipboardPaused?'记录已暂停。':'从启动后开始记录新复制的文本。'}仅在本次运行保留，不发送给模型。</p>
        {data.clipboard.length?<ol className="clipboard-list">{data.clipboard.map(entry=><li key={entry.id}><button disabled={!!busy} onClick={()=>void action('clipboard-copy',entry.id)} aria-label={`复制：${entry.text.slice(0,40)}`} title={entry.text.slice(0,1000)}><span className="clipboard-text">{entry.text}</span><span className="clipboard-time">{copied===entry.id?<><Check size={14}/>已复制</>:time(entry.at)}</span></button></li>)}</ol>:<div className="desktop-empty clipboard-empty"><FileText size={26}/><p>{loading?'正在连接桌面服务…':data.clipboardPaused?'开启记录后，新复制的文字会出现在这里。':'复制一段文字，雪会替你暂存。'}</p><span>最多 10 条 · 自动去重 · 退出即清除</span></div>}
      </section>
    </div><div className="desktop-side-column">
      <section className="desktop-panel media-panel"><div className="desktop-section-heading"><h2><AudioLines size={18}/>正在聆听</h2><span className={'media-playing '+(m.status==='Playing'?'is-playing':'')} aria-label={m.status==='Playing'?'播放中':'未播放'}><i/><i/><i/><i/></span></div>
        {m.available?<><h3>{m.title||'无标题音轨'}</h3><p className="desktop-caption">{m.artist||m.app||'系统媒体播放器'}</p><progress aria-label="播放进度" value={m.position||0} max={Math.max(1,m.duration||1)}/><div className="media-timeline"><span>{duration(m.position)}</span><span>{m.status==='Playing'?'播放中':m.status==='Paused'?'已暂停':m.status||'已停止'}</span><span>{duration(m.duration)}</span></div></>:<div className="desktop-empty"><p>{m.status||'等待一首歌。'}</p><span>读取支持 Windows 系统媒体会话的播放器</span></div>}
      </section>
      <section className="desktop-panel events-panel"><div className="desktop-section-heading"><h2><Clock3 size={18}/>桌面小事</h2><span className="desktop-count">最近 {data.events.length} 条</span></div>
        {data.events.length?<ol className="desktop-events">{data.events.slice(0,6).map((entry,i)=><li key={`${entry.at}-${i}`} className={entry.kind==='failure'?'event-failure':''}><i/><div><p>{entry.text}</p><time>{time(entry.at)}</time></div></li>)}</ol>:<p className="desktop-empty">U 盘接入、接通电源、下载与任务结果，会在这里留下一点回声。</p>}
        <details className="desktop-task-help"><summary><Code2 size={15}/>让雪知道编译结果</summary><p>成功时庆祝，失败时难过。在本项目前端目录 console-v2/frontend 中运行：</p><code>node ../../scripts/yuki-task.cjs -- npm run build</code><p>也可在项目根目录手动通知：</p><code>node scripts/yuki-task.cjs --notify success "编译成功"</code><p>任务投递位置：</p><code>{data.inbox||'启动 Electron 后显示'}</code></details>
      </section>
    </div></div>
  </div>;
}
