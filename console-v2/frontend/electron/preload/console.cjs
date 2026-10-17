'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('yukiHost',Object.freeze({
  kind:'electron',
  request:(name,payload={})=>ipcRenderer.invoke('yuki:request',name,payload),
  subscribe:(onMessage,onDisconnect)=>{
    const message=(_event,value)=>onMessage(value),disconnected=(_event,value)=>onDisconnect(value);
    ipcRenderer.on('yuki:message',message);ipcRenderer.on('yuki:disconnected',disconnected);
    return ()=>{ipcRenderer.removeListener('yuki:message',message);ipcRenderer.removeListener('yuki:disconnected',disconnected);};
  },
  reconnect:()=>ipcRenderer.invoke('yuki:reconnect'),
  exit:()=>ipcRenderer.invoke('yuki:exit'),
}));
