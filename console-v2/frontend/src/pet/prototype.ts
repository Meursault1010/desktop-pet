import {PngRenderer} from './PngRenderer';
import catalog from '../../public/actions/catalog.json';
import './prototype.css';

declare global {interface Window {yukiPrototype:{move:(dx:number,dy:number)=>Promise<void>;setHit:(value:boolean)=>void;close:()=>void}}}
const canvas=document.querySelector<HTMLCanvasElement>('#pet')!;
const renderer=new PngRenderer(canvas);
void renderer.loadCharacter('yuki').then(()=>{document.documentElement.dataset.ready='true';}).catch(error=>{document.documentElement.dataset.error=String(error);});
let drag:{x:number;y:number}|null=null;
canvas.addEventListener('pointerdown',event=>{if(event.button===0){drag={x:event.screenX,y:event.screenY};canvas.setPointerCapture(event.pointerId);}});
canvas.addEventListener('pointermove',event=>{
  if(drag){const dx=event.screenX-drag.x,dy=event.screenY-drag.y;drag={x:event.screenX,y:event.screenY};void window.yukiPrototype.move(dx,dy);return;}
  const rect=canvas.getBoundingClientRect(),x=Math.floor((event.clientX-rect.left)*256/rect.width),y=Math.floor((event.clientY-rect.top)*256/rect.height);
  window.yukiPrototype.setHit((canvas.getContext('2d')?.getImageData(Math.max(0,Math.min(255,x)),Math.max(0,Math.min(255,y)),1,1).data[3]??0)>8);
});
canvas.addEventListener('pointerup',()=>{drag=null;});
canvas.addEventListener('dblclick',()=>void renderer.playAction(catalog.find(action=>action.id==='screen')!,true));
canvas.addEventListener('contextmenu',event=>{event.preventDefault();void renderer.stopAction();});
window.addEventListener('beforeunload',()=>renderer.dispose());
// The prototype intentionally has no behavior sidecar and never creates a second real pet.
