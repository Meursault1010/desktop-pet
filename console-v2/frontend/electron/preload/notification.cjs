'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('yukiNotification',Object.freeze({
  close:()=>ipcRenderer.invoke('yuki:notification-close'),
  onUpdate:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:notification-update',update);return()=>ipcRenderer.removeListener('yuki:notification-update',update);}
}));
