'use strict';
const box=document.getElementById('box');let start,rect,submitted=false;
window.capture.image().then(value=>{const screen=document.getElementById('screen');screen.onload=()=>{screen.hidden=false;};screen.src=value.image;});
document.getElementById('cancel').onclick=()=>window.capture.region(null);
document.addEventListener('keydown',e=>{if(e.key==='Escape')void window.capture.region(null);});
document.addEventListener('pointerdown',e=>{if(e.button!==0||e.target.closest('.capture-help'))return;start={x:e.clientX,y:e.clientY};rect=null;box.hidden=false;document.body.classList.add('dragging');});
document.addEventListener('pointermove',e=>{if(!start)return;const x=Math.max(0,Math.min(innerWidth,e.clientX)),y=Math.max(0,Math.min(innerHeight,e.clientY));rect={x:Math.min(x,start.x),y:Math.min(y,start.y),width:Math.abs(x-start.x),height:Math.abs(y-start.y)};Object.assign(box.style,{left:rect.x+'px',top:rect.y+'px',width:rect.width+'px',height:rect.height+'px'});});
document.addEventListener('pointerup',async()=>{if(!start||submitted)return;start=null;if(!rect||rect.width<5||rect.height<5){box.hidden=true;document.body.classList.remove('dragging');return;}submitted=true;try{await window.capture.region(rect);}catch{submitted=false;document.querySelector('.capture-help span').textContent='框选失败，请重新框选或按 Esc 取消';}});
