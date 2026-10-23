'use strict';
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('capture',Object.freeze({image:()=>ipcRenderer.invoke('yuki:capture-image'),region:region=>ipcRenderer.invoke('yuki:capture-region',region)}));
