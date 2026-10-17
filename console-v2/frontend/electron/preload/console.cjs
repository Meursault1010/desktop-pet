'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('yukiHost',Object.freeze({
  kind:'electron',
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
