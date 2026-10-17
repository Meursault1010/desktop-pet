export type Appearance = { theme: 'light'|'dark'; reduced: boolean; particles: boolean; glow: boolean; slow: boolean };
export function readAppearance(): Appearance {
  const defaults: Appearance = {theme:'light',reduced:false,particles:true,glow:true,slow:false};
  try {
    const stored = JSON.parse(localStorage.getItem('yuki-workbench') || '{}');
    const old = localStorage.getItem('yuki-theme') || localStorage.getItem('xiaoju-theme');
    return {theme: stored.theme === 'dark' || (!stored.theme && old === 'dark') ? 'dark' : 'light',
      reduced:stored.reduced === true,particles:stored.particles !== false,glow:stored.glow !== false,slow:stored.slow === true};
  } catch { return defaults; }
}
export function writeAppearance(value: Appearance) {
  const root=document.documentElement;
  root.dataset.theme=value.theme;root.dataset.motion=value.reduced?'reduced':'full';
  root.dataset.particles=value.particles?'on':'off';root.dataset.glow=value.glow?'on':'off';root.dataset.slow=value.slow?'on':'off';
  try { localStorage.setItem('yuki-workbench',JSON.stringify(value));localStorage.setItem('yuki-theme',value.theme); } catch { /* Session-only appearance remains usable. */ }
}
