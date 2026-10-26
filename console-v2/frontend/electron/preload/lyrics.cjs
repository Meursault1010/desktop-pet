const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('yukiLyrics',Object.freeze({
 snapshot:()=>ipcRenderer.invoke('yuki:lyrics-snapshot'),
 hide:()=>ipcRenderer.invoke('yuki:lyrics-hide'),
 subscribe:listener=>{const update=(_event,value)=>listener(value);ipcRenderer.on('yuki:lyrics-state',update);return()=>ipcRenderer.removeListener('yuki:lyrics-state',update);}
}));
