import {Children,isValidElement,useLayoutEffect,useRef,useState,type DragEvent,type KeyboardEvent,type ReactNode} from 'react';

const STORE_PREFIX='yuki-sort:';
const FLIP_MS=320;
const FLIP_EASE='cubic-bezier(.22,.8,.24,1)';

function loadOrder(scope:string):string[]|null{
 try{const raw=localStorage.getItem(STORE_PREFIX+scope);if(!raw)return null;const list=JSON.parse(raw);return Array.isArray(list)?list.filter((v):v is string=>typeof v==='string'):null;}catch{return null;}
}
function saveOrder(scope:string,order:string[]){
 try{localStorage.setItem(STORE_PREFIX+scope,JSON.stringify(order));}catch{/* 本次会话内仍可用 */}
}

/**
 * Keeps stable keys for every child. When `sortable` is on, the group can be
 * reordered by dragging an item or with Alt + arrow keys; the order is stored
 * per scope in localStorage. Only the visual order changes — each child keeps
 * its own handlers, so tab indexes and section ids stay valid.
 */
export function SortableGroup({scope,children,className='',navigation=false,sortable=false}:{scope:string;children:ReactNode;className?:string;navigation?:boolean;sortable?:boolean;label?:string}){
 const items=Children.toArray(children).filter(isValidElement);
 // Children.toArray prefixes keys (.$foo); persist the readable part only.
 const normalize=(key:string)=>key.replace(/^\.\$?/,'');
 const ids=items.map((child,index)=>normalize(String(child.key??index)));
 const byId=new Map(ids.map((id,index)=>[id,items[index]] as const));
 const [stored,setStored]=useState<string[]|null>(()=>sortable?loadOrder(scope):null);
 const order=stored?[...stored.filter(id=>byId.has(id)),...ids.filter(id=>!stored.includes(id))]:ids;
 const root=useRef<HTMLDivElement>(null);
 const before=useRef(new Map<string,{x:number;y:number}>());
 const [dragging,setDragging]=useState<string|null>(null);
 const [target,setTarget]=useState<{id:string;after:boolean}|null>(null);

 useLayoutEffect(()=>{
  const previous=before.current;
  if(!previous.size)return;
  before.current=new Map();
  const root_=document.documentElement;
  if(root_.dataset.motion==='reduced'||window.matchMedia?.('(prefers-reduced-motion: reduce)').matches)return;
  const duration=root_.dataset.slow==='on'?FLIP_MS*1.6:FLIP_MS;
  root.current?.querySelectorAll<HTMLElement>('[data-sort-id]').forEach(node=>{
   const start=previous.get(node.dataset.sortId??'');
   if(!start)return;
   const rect=node.getBoundingClientRect();
   const dx=start.x-rect.x,dy=start.y-rect.y;
   if(Math.abs(dx)<1&&Math.abs(dy)<1)return;
   node.animate([{transform:`translate(${dx}px,${dy}px)`},{transform:'translate(0,0)'}],{duration,easing:FLIP_EASE});
  });
 });

 function snapshot(){
  const map=new Map<string,{x:number;y:number}>();
  root.current?.querySelectorAll<HTMLElement>('[data-sort-id]').forEach(node=>{
   const id=node.dataset.sortId;
   if(!id)return;
   const rect=node.getBoundingClientRect();
   map.set(id,{x:rect.x,y:rect.y});
  });
  before.current=map;
 }
 function commit(next:string[]){
  snapshot();
  setStored(next);
  saveOrder(scope,next);
 }
 function move(source:string,targetId:string,after:boolean){
  if(source===targetId)return;
  const list=order.filter(id=>id!==source);
  let index=list.indexOf(targetId);
  if(index<0)index=list.length;else if(after)index+=1;
  list.splice(index,0,source);
  commit(list);
 }
 function step(id:string,delta:number){
  const index=order.indexOf(id);
  const next=index+delta;
  if(index<0||next<0||next>=order.length)return;
  const list=[...order];
  list.splice(index,1);
  list.splice(next,0,id);
  commit(list);
 }
 function onDragStart(event:DragEvent<HTMLDivElement>,id:string){
  if(!sortable)return;
  setDragging(id);
  event.dataTransfer.effectAllowed='move';
  try{event.dataTransfer.setData('text/plain',id);}catch{/* 仅用于同组排序 */}
  snapshot();
 }
 function onDragOver(event:DragEvent<HTMLDivElement>,id:string){
  if(!dragging||dragging===id)return;
  event.preventDefault();
  event.dataTransfer.dropEffect='move';
  const rect=event.currentTarget.getBoundingClientRect();
  const parent=event.currentTarget.parentElement;
  const horizontal=parent?getComputedStyle(parent).flexDirection==='row':false;
  const after=horizontal?event.clientX>rect.left+rect.width/2:event.clientY>rect.top+rect.height/2;
  setTarget(current=>current&&current.id===id&&current.after===after?current:{id,after});
 }
 function onDrop(event:DragEvent<HTMLDivElement>,id:string){
  if(!dragging)return;
  event.preventDefault();
  move(dragging,id,target?.id===id?target.after:false);
  setDragging(null);
  setTarget(null);
 }
 function onKeyDown(event:KeyboardEvent<HTMLDivElement>,id:string){
  if(!sortable||!event.altKey)return;
  const delta=event.key==='ArrowUp'||event.key==='ArrowLeft'?-1:event.key==='ArrowDown'||event.key==='ArrowRight'?1:0;
  if(!delta)return;
  event.preventDefault();
  step(id,delta);
 }

 return <div ref={root} className={'sortable-group '+(navigation?'sortable-navigation ':'')+className} data-sort-scope={scope}>
  {order.map(id=>{
   const child=byId.get(id);
   if(!child)return null;
   const state=dragging===id?' is-dragging':target?.id===id?(target.after?' drop-after':' drop-before'):'';
   return <div key={id} data-sort-id={id} className={'sortable-item'+state} draggable={sortable||undefined}
    onDragStart={event=>onDragStart(event,id)} onDragOver={event=>onDragOver(event,id)} onDrop={event=>onDrop(event,id)}
    onDragEnd={()=>{setDragging(null);setTarget(null);}} onKeyDown={event=>onKeyDown(event,id)}>{child}</div>;
  })}
 </div>;
}
