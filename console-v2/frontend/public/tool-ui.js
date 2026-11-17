/* Same-origin preferences keep utility chrome in step with the workbench. */
(() => {
 const root=document.documentElement;
 const read=()=>{
  try{
   const value=JSON.parse(localStorage.getItem('yuki-workbench')||'{}');
   const legacy=localStorage.getItem('yuki-theme')||localStorage.getItem('xiaoju-theme');
   root.dataset.theme=['light','mist','dark'].includes(value.theme)?value.theme:legacy==='dark'?'dark':'mist';
   root.dataset.motion=value.reduced===true?'reduced':'full';root.dataset.slow=value.slow===true?'on':'off';
  }catch{root.dataset.theme='mist';}
 };
 read();window.addEventListener('storage',event=>{if(!event.key||['yuki-workbench','yuki-theme','xiaoju-theme'].includes(event.key))read();});
 window.addEventListener('pageshow',read);
 // Hints stay outside draggable regions and never intercept window gestures.
 document.addEventListener('DOMContentLoaded',()=>{
  const hint=document.createElement('div');hint.id='tool-hint';hint.className='tool-hint';hint.role='tooltip';hint.hidden=true;document.body.append(hint);
  let timer,owner;
  const hide=()=>{clearTimeout(timer);hint.hidden=true;if(owner){const ids=(owner.getAttribute('aria-describedby')||'').split(' ').filter(id=>id&&id!==hint.id);if(ids.length)owner.setAttribute('aria-describedby',ids.join(' '));else owner.removeAttribute('aria-describedby');}owner=null;};
  const show=element=>{hide();owner=element;timer=setTimeout(()=>{if(!element.isConnected)return;hint.textContent=element.dataset.tip;hint.hidden=false;const rect=element.getBoundingClientRect(),width=hint.offsetWidth,height=hint.offsetHeight;hint.style.left=Math.max(8,Math.min(innerWidth-width-8,rect.left+rect.width/2-width/2))+'px';hint.style.top=Math.max(8,rect.bottom+height+14<=innerHeight?rect.bottom+6:rect.top-height-6)+'px';const ids=(element.getAttribute('aria-describedby')||'').split(' ').filter(Boolean);element.setAttribute('aria-describedby',[...new Set([...ids,hint.id])].join(' '));},350);};
  document.addEventListener('pointerover',event=>{const target=event.target.closest('[data-tip]');if(target&&target!==owner)show(target);});
  document.addEventListener('pointerout',event=>{if(owner&&event.target.closest('[data-tip]')===owner&&!owner.contains(event.relatedTarget))hide();});
  document.addEventListener('focusin',event=>{const target=event.target.closest('[data-tip]');if(target)show(target);});
  document.addEventListener('focusout',hide);document.addEventListener('pointerdown',hide);document.addEventListener('keydown',event=>{if(event.key==='Escape')hide();});
  window.addEventListener('blur',hide);window.addEventListener('resize',hide);document.addEventListener('scroll',hide,true);
 });
})();
