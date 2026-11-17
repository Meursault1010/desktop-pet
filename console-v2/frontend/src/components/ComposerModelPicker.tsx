import {useEffect,useId,useRef,useState} from 'react';
import type {KeyboardEvent} from 'react';
import {Check,ChevronDown} from 'lucide-react';

type Props = {
  models:string[];
  value:string;
  disabled:boolean;
  active:boolean;
  onChange:(value:string)=>void;
};

export function ComposerModelPicker({models,value,disabled,active,onChange}:Props){
  const id=useId();
  const trigger=useRef<HTMLButtonElement>(null);
  const menu=useRef<HTMLDivElement>(null);
  const [open,setOpen]=useState(false);

  function placeMenu(){
    const popup=menu.current;
    const rect=trigger.current?.getBoundingClientRect();
    if(!popup||!rect)return;
    const inset=12;
    const gap=6;
    const width=Math.min(340,window.innerWidth-inset*2);
    const above=rect.top-gap-inset;
    const below=window.innerHeight-rect.bottom-gap-inset;
    const placeBelow=above<152&&below>above;
    const left=Math.max(inset,Math.min(rect.right-width,window.innerWidth-width-inset));
    popup.style.width=`${width}px`;
    popup.style.left=`${left}px`;
    popup.style.top=placeBelow?`${rect.bottom+gap}px`:'auto';
    popup.style.bottom=placeBelow?'auto':`${window.innerHeight-rect.top+gap}px`;
    popup.style.maxHeight=`${Math.max(0,Math.min(300,placeBelow?below:above))}px`;
  }

  function closeAndFocus(){
    menu.current?.hidePopover();
    trigger.current?.focus({preventScroll:true});
  }

  useEffect(()=>{
    if(!active||disabled)menu.current?.hidePopover();
  },[active,disabled]);

  useEffect(()=>{
    if(!open)return;
    const followTrigger=(event:Event)=>{
      if(event.target instanceof Node&&menu.current?.contains(event.target))return;
      placeMenu();
    };
    window.addEventListener('resize',placeMenu);
    window.addEventListener('scroll',followTrigger,true);
    return ()=>{
      window.removeEventListener('resize',placeMenu);
      window.removeEventListener('scroll',followTrigger,true);
    };
  },[open]);

  function moveFocus(event:KeyboardEvent<HTMLDivElement>){
    if(event.key==='Escape'){
      event.preventDefault();
      closeAndFocus();
      return;
    }
    if(!['ArrowDown','ArrowUp','Home','End'].includes(event.key))return;
    const items=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role=menuitemradio]'));
    if(!items.length)return;
    event.preventDefault();
    const current=items.findIndex(item=>item===document.activeElement);
    if(event.key==='Home')items[0].focus();
    else if(event.key==='End')items.at(-1)?.focus();
    else if(event.key==='ArrowDown')items[(current+1)%items.length].focus();
    else items[(current<=0?items.length:current)-1].focus();
  }

  return <div className="composer-model-picker">
    <button ref={trigger} type="button" className="composer-model-trigger" popoverTarget={id}
      aria-haspopup="menu" aria-expanded={open} aria-controls={id}
      aria-label={value?`当前模型：${value}`:'选择模型'} disabled={disabled}>
      <span>{value||'选择模型'}</span><ChevronDown aria-hidden="true" size={14}/>
    </button>
    <div id={id} ref={menu} popover="auto" role="menu" aria-label="切换模型" className="composer-model-menu"
      onBeforeToggle={event=>{if(event.newState==='open')placeMenu();}}
      onToggle={event=>{
        const next=event.newState==='open';
        setOpen(next);
        if(next){
          const popup=event.currentTarget;
          (popup.querySelector<HTMLButtonElement>('[aria-checked=true]')||popup.querySelector<HTMLButtonElement>('button'))?.focus();
        }
      }}
      onBlur={event=>{
        if(event.relatedTarget&&!event.currentTarget.contains(event.relatedTarget)&&event.relatedTarget!==trigger.current){
          event.currentTarget.hidePopover();
        }
      }}
      onKeyDown={moveFocus}>
      <p className="composer-model-label" role="presentation">模型</p>
      {models.map(model=><button key={model} type="button" tabIndex={-1} role="menuitemradio" aria-checked={model===value}
        onClick={()=>{if(!disabled){onChange(model);closeAndFocus();}}}>
        <span>{model}</span>{model===value&&<Check aria-hidden="true" size={15}/>}
      </button>)}
    </div>
  </div>;
}
