import { useEffect } from 'react';

/** Only the margins carry starlight; the reading surface stays still. */
export function WorkspaceStars(){
  useEffect(()=>{
    const sync=()=>{document.documentElement.dataset.skyPaused=document.hidden?'true':'false';};
    sync();document.addEventListener('visibilitychange',sync);
    return()=>document.removeEventListener('visibilitychange',sync);
  },[]);
  return <div className="workspace-stars" aria-hidden="true"><svg viewBox="0 0 460 300" fill="none">
    <path className="sky-chart" d="m109 76 72-29 65 43 71-24 68 59M181 47l16 100 87 49 33-130"/>
    <g className="sky-dust">{[[109,76],[181,47],[246,90],[317,66],[385,125],[197,147],[284,196],[405,225],[85,182],[350,262],[150,247],[420,42]].map(([x,y])=><circle key={`${x}-${y}`} cx={x} cy={y} r="1.5"/>)}</g>
    <g className="sky-beacon"><path d="m317 55 2.5 8.5L328 66l-8.5 2.5L317 77l-2.5-8.5L306 66l8.5-2.5Z"/></g>
    <g className="sky-beacon sky-beacon-late"><path d="m197 140 1.6 5.4 5.4 1.6-5.4 1.6-1.6 5.4-1.6-5.4-5.4-1.6 5.4-1.6Z"/></g>
  </svg></div>;
}

/** A sparse celestial signature for yuki's display stage. Never interactive. */
export function StarField(){
  return <svg className="star-field" viewBox="0 0 320 320" fill="none" aria-hidden="true">
    <path className="star-trail" d="M31 110C65 30 235 20 290 102"/>
    <path className="constellation" d="m43 102 29-45 59 13"/>
    <g className="star-points"><circle cx="43" cy="102" r="1.5"/><circle cx="72" cy="57" r="2"/><circle cx="131" cy="70" r="1.3"/><circle cx="280" cy="163" r="1.3"/><circle cx="45" cy="238" r="1.5"/></g>
    <path className="star-glint glint-one" d="m258 53 2.7 9.3L270 65l-9.3 2.7L258 77l-2.7-9.3L246 65l9.3-2.7Z"/>
    <path className="star-glint glint-two" d="m49 161 1.8 6.2L57 169l-6.2 1.8L49 177l-1.8-6.2L41 169l6.2-1.8Z"/>
    <path className="star-glint glint-three" d="m269 228 1.5 5.5 5.5 1.5-5.5 1.5-1.5 5.5-1.5-5.5-5.5-1.5 5.5-1.5Z"/>
  </svg>;
}
