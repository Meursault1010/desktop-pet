'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('yukiHost',Object.freeze({
  kind:'electron',
  quickToolsSync:value=>ipcRenderer.invoke('yuki:quick-tools-sync',value),
  quickToolsSubscribe:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:quick-tool',update);return()=>ipcRenderer.removeListener('yuki:quick-tool',update);},
  workbenchConfig:()=>ipcRenderer.invoke('yuki:workbench-config'),
  workbenchSet:input=>ipcRenderer.invoke('yuki:workbench-set',input),
  windowMode:wide=>ipcRenderer.invoke('yuki:window-mode',wide),
  translationMode:value=>ipcRenderer.invoke('yuki:translation-mode',value),
  translationCapture:()=>ipcRenderer.invoke('yuki:translation-capture'),
  translationSubscribe:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:translation-state',update);return()=>ipcRenderer.removeListener('yuki:translation-state',update);},
  desktopSnapshot:()=>ipcRenderer.invoke('yuki:desktop-snapshot'),
  desktopAction:input=>ipcRenderer.invoke('yuki:desktop-action',input),
  modelConfig:()=>ipcRenderer.invoke('yuki:model-config'),
  modelConfigSet:input=>ipcRenderer.invoke('yuki:model-config-set',input),
  desktopSubscribe:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:desktop-event',update);return ()=>ipcRenderer.removeListener('yuki:desktop-event',update);},
  aiAttach:()=>ipcRenderer.invoke('yuki:ai-attach'),
  aiModels:()=>ipcRenderer.invoke('yuki:ai-models'),
  aiChat:payload=>ipcRenderer.invoke('yuki:ai-chat',payload),
  aiCancel:()=>ipcRenderer.invoke('yuki:ai-cancel'),
  aiSubscribe:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:ai-update',update);return ()=>ipcRenderer.removeListener('yuki:ai-update',update);},
  request:(name,payload={})=>ipcRenderer.invoke('yuki:request',name,payload),
  subscribe:(onMessage,onDisconnect)=>{
    const message=(_event,value)=>onMessage(value),disconnected=(_event,value)=>onDisconnect(value);
    ipcRenderer.on('yuki:message',message);ipcRenderer.on('yuki:disconnected',disconnected);
    return ()=>{ipcRenderer.removeListener('yuki:message',message);ipcRenderer.removeListener('yuki:disconnected',disconnected);};
  },
  reconnect:()=>ipcRenderer.invoke('yuki:reconnect'),
  exit:()=>ipcRenderer.invoke('yuki:exit'),
}));
