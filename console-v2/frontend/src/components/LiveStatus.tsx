import {demo} from '../bridge';
import type {PetSnapshot} from '../bridge';
import {liveStatusView} from '../activityStatus';
export function LiveStatus({state,connected,connecting}:{state:PetSnapshot|null;connected:boolean;connecting:boolean}){
 const view=liveStatusView(state,connected,connecting,demo);
 return <span className={'live-status'+(view.live?' is-live':'')} data-state={view.key} role="status" aria-live="polite" aria-label={'雪现在：'+view.label} title={view.detail?view.label+' · '+view.detail:view.label}>
  <i aria-hidden="true"/><span className="live-status-text">{view.label}</span>
 </span>;
}
