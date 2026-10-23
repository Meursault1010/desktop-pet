export type Appearance = { theme: 'light'|'mist'|'dark'; reduced: boolean; particles: boolean; glow: boolean; slow: boolean };
export function readAppearance(): Appearance {
 const defaults:Appearance={theme:'mist',reduced:false,particles:true,glow:false,slow:false};
 try {const s=JSON.parse(localStorage.getItem('yuki-workbench')||'{}');const old=localStorage.getItem('yuki-theme')||localStorage.getItem('xiaoju-theme');return {...defaults,theme:['light','mist','dark'].includes(s.theme)?s.theme:old==='dark'?'dark':'mist',reduced:s.reduced===true,particles:s.particles!==false,glow:s.glow===true,slow:s.slow===true};}catch{return defaults;}
}
export function writeAppearance(value:Appearance){
 const r=document.documentElement;r.dataset.theme=value.theme;r.dataset.motion=value.reduced?'reduced':'full';r.dataset.particles=value.particles?'on':'off';r.dataset.glow=value.glow?'on':'off';r.dataset.slow=value.slow?'on':'off';
 try{localStorage.setItem('yuki-workbench',JSON.stringify(value));localStorage.setItem('yuki-theme',value.theme);}catch{/* Remains usable for this session. */}
}
