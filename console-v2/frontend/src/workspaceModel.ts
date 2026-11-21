export type WidgetType='companion'|'journal'|'rhythm'|'system'|'focus'|'todos'|'clipboard'|'translation';
export type Widget={id:string;type:WidgetType;title:string;width:1|2|3;height:number};
export type WorkspacePage={id:string;name:string;widgets:Widget[]};
export type Todo={id:string;text:string;due:string;done:boolean;notified?:boolean};
export type Focus={end:number|null;remaining:number;duration:number;breakDuration:number;completed:number;completedDate?:string;mode:'focus'|'break'};
export const widgetNames:Record<WidgetType,string>={companion:'雪的此刻 · 时钟与天气',journal:'今日足迹',rhythm:'陪伴节奏',system:'电脑状态',focus:'专注计时',todos:'待办摘要',clipboard:'剪贴板摘要',translation:'划词翻译'};
export function makeWidget(type:WidgetType):Widget{return {id:crypto.randomUUID(),type,title:widgetNames[type],width:type==='companion'?3:type==='journal'?2:1,height:type==='companion'?210:260};}
export function defaultPages():WorkspacePage[]{return [{id:'default',name:'默认总览',widgets:(['companion','journal','rhythm','system'] as WidgetType[]).map(makeWidget)}];}
export function readStore<T>(key:string,fallback:T):T{try{return JSON.parse(localStorage.getItem('yuki-v2-'+key)||'null')??fallback;}catch{return fallback;}}
export function saveStore(key:string,value:unknown){localStorage.setItem('yuki-v2-'+key,JSON.stringify(value));}

export function validTodos(value:unknown):Todo[]{
 return Array.isArray(value)?value.filter(t=>t&&typeof t.id==='string'&&typeof t.text==='string'&&t.text.trim()).slice(0,200).map(t=>({id:t.id,text:t.text.slice(0,200),done:t.done===true,notified:t.notified===true,due:typeof t.due==='string'&&Number.isFinite(Date.parse(t.due))?t.due:''})):[];
}
export function validFocus(value:unknown):Focus{
 const f=(value&&typeof value==='object'?value:{}) as Partial<Focus>;const duration=Number.isInteger(f.duration)&&f.duration!>=1&&f.duration!<=180?f.duration!:25;const breakDuration=Number.isInteger(f.breakDuration)&&f.breakDuration!>=1&&f.breakDuration!<=60?f.breakDuration!:5;
 return {duration,breakDuration,end:typeof f.end==='number'&&Number.isFinite(f.end)&&f.end>0?Math.min(f.end,Date.now()+21600000):null,remaining:typeof f.remaining==='number'&&Number.isFinite(f.remaining)?Math.max(0,Math.min(duration*60,f.remaining)):duration*60,completed:typeof f.completed==='number'?Math.max(0,Math.floor(f.completed)):0,completedDate:typeof f.completedDate==='string'?f.completedDate:undefined,mode:f.mode==='break'?'break':'focus'};
}
export function validHealth(value:unknown){const v=(value&&typeof value==='object'?value:{}) as {enabled?:boolean;minutes?:number;next?:number};return {enabled:v.enabled===true,minutes:Number.isInteger(v.minutes)&&v.minutes!>=1&&v.minutes!<=240?v.minutes!:50,next:typeof v.next==='number'&&Number.isFinite(v.next)?v.next:0};}
