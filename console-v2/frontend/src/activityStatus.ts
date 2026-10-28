import type {PetSnapshot} from './bridge';
export type LiveStatusView={key:string;label:string;detail:string;live:boolean};
export function liveStatusView(state:PetSnapshot|null,connected:boolean,connecting:boolean,preview=false):LiveStatusView{
 if(preview)return {key:'preview',label:state?.activity?.label||state?.status||'界面预览',detail:'界面预览，不连接真实宠物',live:false};
 if(!connected)return connecting
  ?{key:'connecting',label:'正在连接桌宠…',detail:'等待桌面宠物响应',live:false}
  :{key:'offline',label:'桌宠未连接',detail:'状态暂时无法同步',live:false};
 const activity=state?.activity;
 return {key:activity?.key||'pending',label:activity?.label||state?.status||'正在读取状态',detail:activity?.detail||'',live:true};
}
