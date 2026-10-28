import {Children,isValidElement,type ReactNode} from 'react';

/** Fixed page order: keep stable React keys and the shared group spacing only. */
export function SortableGroup({scope,children,className='',navigation=false}:{scope:string;children:ReactNode;className?:string;navigation?:boolean;label?:string}){
 const items=Children.toArray(children).filter(isValidElement);
 return <div className={'sortable-group '+(navigation?'sortable-navigation ':'')+className} data-sort-scope={scope}>
  {items.map((child,index)=>{const id=String(child.key??index);return <div key={id} data-sort-id={id} className="sortable-item">{child}</div>;})}
 </div>;
}
