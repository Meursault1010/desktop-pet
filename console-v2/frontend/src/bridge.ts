import { host } from './host';

export type Preferences = { size: number; opacity: number; always_on_top: boolean; speed: number; activity: string; random_movement: boolean; autonomous_play: boolean; autonomous_icons: boolean; autonomous_speech: boolean; greeting: boolean; quiet: boolean; paused: boolean; auto_snap: boolean; music_reactions: boolean; focus_companion: boolean; focus_click_through: boolean; autonomous_windows: boolean; relationship_memory: boolean };
export type DesktopIcon = {id:string; name:string; folder:boolean; available?:boolean; rect:{x:number;y:number;width:number;height:number}};
export type IconSleepOptions = {direction:string; offset_x:number; offset_y:number; breath:number; duration:number; snap_distance:number};
export type IconSleepState = {icons:DesktopIcon[];options:IconSleepOptions;phase:string;target_id:string|null;direction:string;message:string;error:string;scanning:boolean};
export type EdgeOptions = {enabled:boolean;windows:boolean;screens:boolean;corner:'left'|'right';delay:number};
export type EdgeState = {options:EdgeOptions;active:boolean;kind:string;message:string;error:string;direction:string};
export type MusicState = {enabled:boolean;listening:boolean;source:string;error:string;kind:string;label:string;bpm:number;level:number;bands:number[];reaction:string;suspended:boolean;suspend_reason?:string};
export type FocusState = {active:boolean;phase:'idle'|'focus'|'break';remaining:number;click_through:boolean;enabled:boolean;session_minutes:number};
export type MemoryState = {enabled:boolean;first_seen:string;last_interaction:string;days_together:number;clicks:number;headpats:number;focus_minutes:number;greetings:number;today:{clicks:number;headpats:number;focus_minutes:number;greetings:number};error:string};
export type WindowPerchState = {enabled:boolean;active:boolean;leaping:boolean;phase:string;message:string;error:string};
export type PetSnapshot = { preferences: Preferences; status: string; visible: boolean; position: { x: number; y: number }; screen: string; storage_error: boolean; revision: number; config_path: string; icon_sleep?:IconSleepState;edge_attachment?:EdgeState;routine?:{key:string;name:string;resting:boolean};patrol?:{active:boolean;exploring?:boolean;phase:string;activity:string;task_id?:number;target_id?:string|null;target?:string;path_probe_ms?:number;next_intent?:string;reason?:string;energy?:number;curiosity?:number};music?:MusicState;focus?:FocusState;memory?:MemoryState;window_perch?:WindowPerchState;idle?:{state:string|null;name:string;action_id:string|null;automatic:boolean;phase:string};sleep?:{phase:string;sleeping:boolean;scheduled:boolean;resume_in:number;schedule:string;wake_reason:string} };
export type Message = { type: string; name?: string; state?: PetSnapshot; preview?: string };
export const defaults: Preferences = { size: 100, opacity: 100, always_on_top: true, speed: 48, activity: '默认', random_movement: true, autonomous_play: true, autonomous_icons: true, autonomous_speech: true, greeting: true, quiet: false, paused: false, auto_snap: true, music_reactions: true, focus_companion: true, focus_click_through: false, autonomous_windows: true, relationship_memory: true };
export const demo = new URLSearchParams(location.search).get('demo') === '1' && !host;
let demoState: PetSnapshot = { preferences: { ...defaults }, status: '待机', visible: true, position: { x: 1420, y: 820 }, screen: '预览显示器', storage_error: false, revision: 0, config_path: '演示模式，不写入设置' };
let demoListener: ((message: Message) => void) | undefined;
let jumpTimer: number | undefined;
function updateStatus() { demoState.status = !demoState.visible ? '已隐藏' : demoState.preferences.quiet ? '安静模式' : demoState.preferences.paused ? '已暂停' : '待机'; }
export async function command(name: string, payload: Record<string, unknown> = {}): Promise<Message> {
  if (demo) {
    if (name === 'set_preference') demoState.preferences = { ...demoState.preferences, [String(payload.key)]: payload.value };
    if (name === 'set_visible') demoState.visible = Boolean(payload.visible);
    if (name === 'reset_defaults') demoState.preferences = { ...defaults };
    updateStatus();
    if (name === 'jump') {
      demoState.status = '跳跃中';
      window.clearTimeout(jumpTimer);
      jumpTimer = window.setTimeout(() => { updateStatus(); demoState.revision++; demoListener?.({ type: 'event', state: structuredClone(demoState) }); }, 650);
    }
    demoState.revision++;
    return { type: 'response', state: structuredClone(demoState), preview: '/pet-preview.png' };
  }
  if (!host) throw new Error('请通过项目中的启动脚本打开桌面控制台');
  return host.request(name, payload);
}
export async function subscribe(onMessage: (message: Message) => void, onDisconnect: (reason: string) => void) {
  if (demo) { demoListener = onMessage; return () => { if (demoListener === onMessage) demoListener = undefined; }; }
  if (!host) return () => {};
  return host.subscribe(onMessage, onDisconnect);
}
export async function reconnect() { await host?.reconnect(); }
export async function exitApp() { await host?.exit(); }
