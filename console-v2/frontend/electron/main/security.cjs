'use strict';
const path=require('node:path');
const CSP="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'none'";
function resourcePath(url,root) {
  const parsed=new URL(url);
  if(parsed.protocol!=='yuki:'||parsed.host!=='app')throw new Error('Forbidden origin');
  const relative=decodeURIComponent(parsed.pathname);
  if(relative.includes('\\')||relative.includes('\0')||relative.split('/').includes('..'))throw new Error('Forbidden path');
  const target=path.resolve(root,'.'+(relative==='/'?'/index.html':relative));
  const rel=path.relative(root,target);
  if(rel.startsWith('..')||path.isAbsolute(rel))throw new Error('Forbidden path');
  return target;
}
function trusted(event,window) {
  if(!window||window.isDestroyed()||event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame)return false;
  try {const url=new URL(event.senderFrame.url);return url.protocol==='yuki:'&&url.host==='app';}catch{return false;}
}
function webPreferences(preload) {return {preload,nodeIntegration:false,contextIsolation:true,sandbox:true,webSecurity:true,webviewTag:false};}
function harden(window) {
  window.webContents.setWindowOpenHandler(()=>({action:'deny'}));
  window.webContents.on('will-navigate',event=>event.preventDefault());
  window.webContents.on('will-attach-webview',event=>event.preventDefault());
}
function closeBehavior({quitting,trayReady}) {return quitting?'close':trayReady?'hide':'minimize';}
module.exports={CSP,resourcePath,trusted,webPreferences,harden,closeBehavior};
