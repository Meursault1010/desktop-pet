'use strict';
const $=id=>document.getElementById(id);let current;
function render(state){
 current=state;const loading=['loading','ocr'].includes(state.phase),error=state.phase==='error';
 $('direction').textContent=state.target==='English'?'中文 → English':state.target?'外语 → 中文':'划线翻译';
 $('status').className='status'+(loading?' loading':error?' error':'');
 $('status').textContent=state.error||(state.phase==='ocr'?'正在识别框选区域…':loading?'雪正在翻译…':'');
 $('status').hidden=!loading&&!state.error;$('result').textContent=state.text||'';$('source').textContent=state.source||'';
 $('original').hidden=!state.source;$('copy').disabled=state.phase!=='done'||!state.text;$('copy').querySelector('span').textContent='复制译文';
 $('retry').hidden=!error||!state.source;$('method').textContent=(state.method==='ocr'?'本地 OCR + Qwen':'本地 Qwen')+' · 仅本次显示';
}
window.translation.subscribe(render);window.translation.snapshot().then(state=>{if(!current)render(state);});
async function control(name){try{await window.translation.control(name);if(name==='copy')$('copy').querySelector('span').textContent='已复制';}catch{$('status').hidden=false;$('status').textContent='操作失败，请重试';}}
$('close').onclick=()=>control('close');$('copy').onclick=()=>control('copy');$('retry').onclick=()=>control('retry');
document.addEventListener('keydown',event=>{if(event.key==='Escape')void control('close');});
// Pointer capture keeps dragging continuous even when the pointer leaves the window.
// Capture event coordinates immediately so queued IPC cannot lose a quick gesture.
function draggable(element,kind){
 let pointer=null,frame=null,point=null;
 const position=event=>({x:event.screenX,y:event.screenY});
 const send=input=>window.translation.gesture(input).catch(()=>{
  const active=pointer;pointer=null;delete element.dataset.dragging;
  if(frame!==null){cancelAnimationFrame(frame);frame=null;}
  if(active!==null&&element.hasPointerCapture(active))element.releasePointerCapture(active);
 });
 element.addEventListener('pointerdown',event=>{
  if(event.button!==0||(kind==='move'&&event.target.closest('button'))||pointer!==null)return;
  event.preventDefault();pointer=event.pointerId;point=position(event);element.setPointerCapture(pointer);element.dataset.dragging='true';void send({phase:'start',kind,...point});
 });
 element.addEventListener('pointermove',event=>{
  if(event.pointerId!==pointer)return;
  point=position(event);if(frame!==null)return;
  frame=requestAnimationFrame(()=>{frame=null;void send({phase:'update',...point});});
 });
 const end=event=>{
  if(event.pointerId!==pointer)return;
  if(frame!==null){cancelAnimationFrame(frame);frame=null;}
  void send({phase:'update',...(event.type==='pointerup'?position(event):point)});void send({phase:'end'});pointer=null;delete element.dataset.dragging;
  if(element.hasPointerCapture(event.pointerId))element.releasePointerCapture(event.pointerId);
 };
 element.addEventListener('pointerup',end);element.addEventListener('pointercancel',end);element.addEventListener('lostpointercapture',end);
}
draggable(document.querySelector('header'),'move');draggable($('resize'),'resize');
let keyboardResize=Promise.resolve();
$('resize').addEventListener('keydown',event=>{
 const delta={ArrowLeft:[-16,0],ArrowRight:[16,0],ArrowUp:[0,-16],ArrowDown:[0,16]}[event.key];
 if(!delta)return;event.preventDefault();
 keyboardResize=keyboardResize.then(()=>window.translation.gesture({phase:'start',kind:'resize',x:0,y:0})).then(()=>window.translation.gesture({phase:'update',x:delta[0],y:delta[1]})).finally(()=>window.translation.gesture({phase:'end'})).catch(()=>{});
});
