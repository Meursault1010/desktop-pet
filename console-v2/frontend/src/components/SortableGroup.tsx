import {Children,isValidElement,useLayoutEffect,useRef,useState,type ReactNode} from 'react';
import {GripVertical} from 'lucide-react';
import {normalizeOrder,moveItem} from '../sortOrder';

/** Independent scopes preserve React keys and never move live controls across forms. */
export function SortableGroup({scope,children,className='',navigation=false,label='内容'}:{scope:string;children:ReactNode;className?:string;navigation?:boolean;label?:string}){
 const items=Children.toArray(children).filter(isValidElement);
 const ids=items.map((child,i)=>String(child.key??i));
 const key='yuki-v2-order-'+scope;
 const [saved,setSaved]=useState<unknown>(()=>{try{return JSON.parse(localStorage.getItem(key)||'null');}catch{return null;}});
 const order=normalizeOrder(saved,ids),root=useRef<HTMLDivElement>(null),rects=useRef(new Map<string,DOMRect>()),animations=useRef<Animation[]>([]);
 const [drag,setDrag]=useState<string|null>(null),[over,setOver]=useState<string|null>(null),[message,setMessage]=useState('');
 const active=useRef<string|null>(null);
 const commit=(from:string,to:string)=>{const next=moveItem(order,from,to);setSaved(next);try{localStorage.setItem(key,JSON.stringify(next));setMessage('位置已调整并保存');}catch{setMessage('位置已调整，但本机存储不可用');}};
 useLayoutEffect(()=>{
  const next=new Map<string,DOMRect>();
  animations.current.forEach(a=>a.cancel());animations.current=[];
  for(const el of Array.from(root.current?.children||[])){
   if(!(el instanceof HTMLElement)||!el.dataset.sortId)continue;
   const id=el.dataset.sortId,r=el.getBoundingClientRect(),old=rects.current.get(id);next.set(id,r);
   if(old&&document.documentElement.dataset.motion!=='reduced'&&!matchMedia('(prefers-reduced-motion: reduce)').matches){
    const x=old.x-r.x,y=old.y-r.y;
    if(Math.abs(x)+Math.abs(y)>1)animations.current.push(el.animate([{transform:`translate(${x}px,${y}px)`},{transform:'translate(0,0)'}],{duration:260,easing:'cubic-bezier(.16,1,.3,1)'}));
   }
  }rects.current=next;
 },[order.join('|')]);
 useLayoutEffect(()=>()=>{animations.current.forEach(a=>a.cancel());},[]);
 const finish=()=>{active.current=null;setDrag(null);setOver(null);};
 return <div ref={root} className={'sortable-group '+(navigation?'sortable-navigation ':'')+className} data-sort-scope={scope} onKeyDownCapture={e=>{if(e.key==='Escape')finish();}}>
 {order.map(id=>{const child=items[ids.indexOf(id)],name=(child.props as {label?:string;'aria-label'?:string}).label||(child.props as {'aria-label'?:string})['aria-label']||label;
 return <div key={id} data-sort-id={id} className={'sortable-item '+(drag===id?'is-dragging ':'')+(over===id&&drag!==id?'is-drop-target':'')} title={navigation?'拖动调整顺序；也可按 Alt + 方向键':undefined} draggable={navigation} onDragStart={e=>{e.stopPropagation();if(!navigation&&!(e.target as HTMLElement).closest('.sort-grip')){e.preventDefault();return;}const r=e.currentTarget.getBoundingClientRect();e.dataTransfer.setDragImage(e.currentTarget,Math.max(0,e.clientX-r.left),Math.max(0,e.clientY-r.top));active.current=id;setDrag(id);e.dataTransfer.effectAllowed='move';e.dataTransfer.setData('text/plain',scope+':'+id);}} onDragOver={e=>{e.stopPropagation();if(active.current&&active.current!==id){e.preventDefault();e.dataTransfer.dropEffect='move';setOver(id);}}} onDragLeave={e=>{if(!e.currentTarget.contains(e.relatedTarget as Node))setOver(null);}} onDrop={e=>{e.stopPropagation();if(active.current){e.preventDefault();commit(active.current,id);finish();}}} onDragEnd={e=>{e.stopPropagation();finish();}} onKeyDown={e=>{if(!e.altKey||!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key))return;if(!navigation&&!(e.target as HTMLElement).closest('.sort-grip'))return;e.preventDefault();e.stopPropagation();const i=order.indexOf(id),step=['ArrowUp','ArrowLeft'].includes(e.key)?-1:1;if(order[i+step])commit(id,order[i+step]);}}>
 {!navigation&&<button type="button" className="sort-grip" draggable aria-label={'调整'+name+'位置'} title="拖动调整位置；也可按 Alt + 方向键"><GripVertical size={14}/></button>}{child}
 </div>;})}<span className="sort-announcement" role="status" aria-live="polite">{message}</span>
 </div>;
}
