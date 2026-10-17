const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('yukiPrototype',Object.freeze({
  move:(dx,dy)=>ipcRenderer.invoke('yuki:prototype-move',dx,dy),
  setHit:value=>ipcRenderer.send('yuki:prototype-hit',value),
  close:()=>ipcRenderer.send('yuki:prototype-close'),
}));
