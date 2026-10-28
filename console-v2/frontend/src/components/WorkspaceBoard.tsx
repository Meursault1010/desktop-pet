import type {CSSProperties,ReactNode} from 'react';
import {defaultPages,type WidgetType} from '../workspaceModel';

const page=defaultPages()[0];
const defaultShape=page.widgets.map(w=>w.type).join(',')==='companion,journal,rhythm,system'
 &&page.widgets.every((w,i)=>w.width===[3,2,1,1][i]);

export function WorkspaceBoard({render}:{render:(type:WidgetType)=>ReactNode}){
 return <section className="workspace-board" aria-label="总览工作区">
  <div className="board-toolbar"><div className="workspace-tabs"><span>默认总览</span></div></div>
  <div className={'widget-grid '+(defaultShape?'editorial-layout default-layout':'')}>
   {page.widgets.map(w=><section className={'workspace-widget widget-'+w.type} key={w.id} data-widget={w.id} data-width={w.width} style={{'--span':w.width,'--height':w.height+'px'} as CSSProperties}>
    <div className="widget-heading"><h2>{w.title}</h2></div>
    <div className="widget-content">{render(w.type)}</div>
   </section>)}
  </div>
 </section>;
}
