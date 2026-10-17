import { invoke, isTauri } from '@tauri-apps/api/core';
import { listen } from '@tauri-apps/api/event';

export type Preferences = { size: number; opacity: number; always_on_top: boolean; speed: number; activity: string; random_movement: boolean; greeting: boolean; quiet: boolean; paused: boolean; auto_snap: boolean };
export type DesktopIcon = {id:string; name:string; folder:boolean; available?:boolean; rect:{x:number;y:number;width:number;height:number}};
export type IconSleepOptions = {direction:string; offset_x:number; offset_y:number; breath:number; duration:number; auto_snap:boolean; snap_distance:number};
export type IconSleepState = {icons:DesktopIcon[];options:IconSleepOptions;phase:string;target_id:string|null;direction:string;message:string;error:string;scanning:boolean};
export type EdgeOptions = {enabled:boolean;windows:boolean;screens:boolean;corner:'left'|'right';delay:number};
export type EdgeState = {options:EdgeOptions;active:boolean;kind:string;message:string;error:string;direction:string};
export type PetSnapshot = { preferences: Preferences; status: string; visible: boolean; position: { x: number; y: number }; screen: string; storage_error: boolean; revision: number; config_path: string; icon_sleep?:IconSleepState;edge_attachment?:EdgeState };
export type Message = { type: string; name?: string; state?: PetSnapshot; preview?: string };
export const defaults: Preferences = { size: 100, opacity: 100, always_on_top: true, speed: 48, activity: '默认', random_movement: true, greeting: true, quiet: false, paused: false, auto_snap: true };
export const demo = new URLSearchParams(location.search).get('demo') === '1' && !isTauri();
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
  if (!isTauri()) throw new Error('请通过项目中的 start.bat 打开桌面控制台');
  return invoke<Message>('pet_command', { name, payload });
}
export async function subscribe(onMessage: (message: Message) => void, onDisconnect: (reason: string) => void) {
  if (demo) { demoListener = onMessage; return () => { if (demoListener === onMessage) demoListener = undefined; }; }
  if (!isTauri()) return () => {};
  const stop = await listen<Message>('pet-message', event => onMessage(event.payload));
  try {
    const disconnect = await listen<string>('pet-disconnected', event => onDisconnect(event.payload));
    return () => { stop(); disconnect(); };
  } catch (error) { stop(); throw error; }
}
export async function reconnect() { if (isTauri()) await invoke('restart_pet'); }
export async function exitApp() { if (isTauri()) await invoke('exit_app'); }
