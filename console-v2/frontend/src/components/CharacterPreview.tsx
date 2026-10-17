import { useEffect, useRef, useState, type CSSProperties } from 'react';
import { host } from '../host';
import { PngRenderer } from '../pet/PngRenderer';

export function CharacterPreview({source,animated=true,opacity=1,scale=1,caption='PNG / CHARACTER PREVIEW'}:{source:string;animated?:boolean;opacity?:number;scale?:number;caption?:string}) {
  const canvas=useRef<HTMLCanvasElement>(null),[ready,setReady]=useState(false);
  useEffect(()=>{
    const media=matchMedia('(prefers-reduced-motion: reduce)');let renderer:PngRenderer|undefined,disposed=false;
    const sync=()=>{
      renderer?.dispose();renderer=undefined;setReady(false);
      if(!canvas.current||!animated||media.matches||document.hidden||host?.kind!=='electron')return;
      const instance=new PngRenderer(canvas.current);renderer=instance;
      void instance.loadCharacter('yuki').then(()=>{if(!disposed&&renderer===instance)setReady(true);}).catch(()=>{if(renderer===instance){instance.dispose();renderer=undefined;}});
    };
    sync();media.addEventListener('change',sync);document.addEventListener('visibilitychange',sync);
    return()=>{disposed=true;renderer?.dispose();media.removeEventListener('change',sync);document.removeEventListener('visibilitychange',sync);};
  },[animated]);
  return <div className="character-stage"><div className="stage-aura"/><div className="stage-orbits"><i/><i/><i/></div><span className="stage-cross cross-a">+</span><span className="stage-cross cross-b">+</span><div className="stage-particles">{[0,1,2,3,4,5].map(i=><i key={i} style={{'--i':i} as CSSProperties}/>)}</div><div className={'character-visual '+(animated?'breathing':'')} style={{opacity,transform:`scale(${scale})`}}><img hidden={ready} src={source} alt="yuki，白发蓝裙的猫耳伙伴" draggable={false}/><canvas hidden={!ready} ref={canvas} width={320} height={320} aria-label="yuki PNG 呼吸与眨眼预览"/></div><span className="stage-caption">{caption}</span></div>;
}
