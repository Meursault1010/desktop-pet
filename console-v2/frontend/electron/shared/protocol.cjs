'use strict';
const VERSION = 1;
const MAX_LINE = 2_000_000;
const MAX_REQUEST = 65_536;
const COMMANDS = new Set(['get_state', 'set_preference', 'set_visible', 'toggle_visibility',
  'toggle_pause', 'jump', 'go_home', 'go_corner', 'patrol_once', 'stop_patrol', 'set_focus', 'reset_defaults', 'shutdown', 'play_action', 'stop_action',
  'refresh_desktop_icons', 'configure_icon_sleep', 'start_icon_sleep', 'stop_icon_sleep',
  'configure_ui', 'configure_edge_attachment', 'stop_edge_attachment', 'speech_update', 'wake_sleep', 'desktop_event', 'quick_tools_update',
  'reset_companion_memory', 'perch_window', 'stop_window_perch']);
const empty = new Set([...COMMANDS].filter(c => !['set_focus','configure_ui','set_preference','set_visible','play_action',
  'configure_icon_sleep','start_icon_sleep','configure_edge_attachment','speech_update','desktop_event','quick_tools_update'].includes(c)));
function object(v) { return v !== null && typeof v === 'object' && !Array.isArray(v); }
function keys(v, allowed) { if (Object.keys(v).some(k => !allowed.includes(k))) throw new Error('未知参数'); }
function integer(v, min, max) { return Number.isInteger(v) && v >= min && v <= max; }
function boolean(v) { return typeof v === 'boolean'; }
function preference(key, value) {
  const limits = {size:[50,200], opacity:[30,100], speed:[10,150]};
  if (Object.hasOwn(limits,key)) return integer(value,...limits[key]);
  if (key === 'activity') return ['少动','默认','活跃'].includes(value);
  return ['always_on_top','random_movement','autonomous_play','autonomous_icons','autonomous_speech','greeting','quiet','paused','auto_snap','music_reactions','focus_companion','focus_click_through','autonomous_windows','relationship_memory'].includes(key) && boolean(value);
}
function validate(name, payload = {}) {
  if (!COMMANDS.has(name) || !object(payload)) throw new Error('不支持的命令或参数');
  if (Buffer.byteLength(JSON.stringify(payload)) > MAX_REQUEST - 256) throw new Error('请求过大');
  if (empty.has(name)) keys(payload, []);
  if(name==='quick_tools_update'){keys(payload,['ready','clipboard','clipboardPaused','focus','todos','todoCount','error']);if(typeof payload.ready!=='boolean'||!Array.isArray(payload.clipboard)||payload.clipboard.length>10||!Array.isArray(payload.todos)||payload.todos.length>5||typeof payload.error!=='string'||payload.error.length>200)throw Error('快捷工具状态无效');}
  if(name==='set_focus'){
    keys(payload,['enabled','phase','remaining']);
    if(typeof payload.enabled!=='boolean'||('phase' in payload&&!['focus','break'].includes(payload.phase))||('remaining' in payload&&!integer(payload.remaining,0,86400)))throw Error('专注状态无效');
  }
  if(name==='configure_ui'){keys(payload,['theme','bubble','reduced','translation']);if(!['light','mist','dark'].includes(payload.theme)||!['light','mist','dark'].includes(payload.bubble)||typeof payload.reduced!=='boolean'||typeof payload.translation!=='boolean')throw Error('界面设置无效');}
  if(name==='desktop_event'){
    keys(payload,['kind','text']);
    if(!['usb','charging','download','success','failure','thinking','working','waiting','done','error'].includes(payload.kind)||typeof payload.text!=='string'||payload.text.length>180)throw new Error('桌面事件无效');
  }
  if (name === 'speech_update') {
    keys(payload,['id','phase','text']);
    if (typeof payload.id !== 'string' || !/^[a-zA-Z0-9-]{1,80}$/.test(payload.id) ||
        !['thinking','answer','done','error'].includes(payload.phase) ||
        typeof payload.text !== 'string' || payload.text.length > 6000) throw new Error('气泡消息无效');
  }
  if (name === 'set_preference') {
    keys(payload,['key','value']);
    if (typeof payload.key !== 'string' || !preference(payload.key,payload.value)) throw new Error('设置值无效');
  }
  if (name === 'set_visible') { keys(payload,['visible']); if (!boolean(payload.visible)) throw new Error('显示状态无效'); }
  if (name === 'start_icon_sleep') {
    keys(payload,['icon_id']);
    if (typeof payload.icon_id !== 'string' || !payload.icon_id || payload.icon_id.length > 4096) throw new Error('图标编号无效');
  }
  if (name === 'play_action') {
    keys(payload,['action_id','loop','speed']);
    if (typeof payload.action_id !== 'string' || !/^[a-z0-9-]{1,80}$/.test(payload.action_id) ||
        ('loop' in payload && !boolean(payload.loop)) || ('speed' in payload &&
        !(typeof payload.speed === 'number' && Number.isFinite(payload.speed) && payload.speed >= .25 && payload.speed <= 2))) throw new Error('动作参数无效');
  }
  if (name === 'configure_icon_sleep') {
    const tests = {direction:v=>['auto','left','right','back','front','sit-front','sit-back','prone-front','prone-back','perch-front','perch-back'].includes(v),
      offset_x:v=>integer(v,-100,100),offset_y:v=>integer(v,-100,100),breath:v=>integer(v,0,100),
      duration:v=>integer(v,0,120),auto_snap:boolean,snap_distance:v=>integer(v,30,240)};
    keys(payload,Object.keys(tests));
    if (Object.entries(payload).some(([k,v])=>!tests[k](v))) throw new Error('依靠参数无效');
  }
  if (name === 'configure_edge_attachment') {
    const tests = {enabled:boolean,windows:boolean,screens:boolean,corner:v=>['left','right'].includes(v),delay:v=>integer(v,2,60)};
    keys(payload,Object.keys(tests));
    if (Object.entries(payload).some(([k,v])=>!tests[k](v))) throw new Error('边缘参数无效');
  }
  return {name,payload};
}
function validateMessage(v) {
  if (!object(v) || !['ready','response','event'].includes(v.type)) throw new Error('后端协议消息无效');
  if (v.type === 'ready' && v.protocol !== VERSION) throw new Error('后端协议版本不兼容');
  if (v.type === 'response' && (typeof v.id !== 'string' || typeof v.ok !== 'boolean')) throw new Error('响应编号无效');
  if (v.state && (!object(v.state) || !object(v.state.preferences) || !Number.isInteger(v.state.revision))) throw new Error('状态快照无效');
  return v;
}
module.exports = {VERSION,MAX_LINE,MAX_REQUEST,COMMANDS,validate,validateMessage};
