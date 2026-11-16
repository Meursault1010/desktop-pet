'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('translation',Object.freeze({
 snapshot:()=>ipcRenderer.invoke('yuki:translation-view'),
 edit:source=>ipcRenderer.invoke('yuki:translation-edit',source),
 control:name=>ipcRenderer.invoke('yuki:translation-control',name),
 gesture:input=>ipcRenderer.invoke('yuki:translation-gesture',input),
 subscribe:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:translation-result',update);return()=>ipcRenderer.removeListener('yuki:translation-result',update);}
}));
