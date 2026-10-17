const path=require('node:path');
const {ipcMain,screen}=require('electron');
const {webPreferences,harden,trusted}=require('./security.cjs');
async function launch({app,BrowserWindow,smoke}){
  const area=screen.getPrimaryDisplay().workArea;
  const pet=new BrowserWindow({width:256,height:256,x:area.x+area.width-286,y:area.y+area.height-256,
    transparent:true,frame:false,alwaysOnTop:true,skipTaskbar:true,resizable:false,hasShadow:false,show:!smoke,
    webPreferences:{...webPreferences(path.join(__dirname,'../preload/prototype.cjs')),backgroundThrottling:false}});
  harden(pet);
  const guard=event=>{if(!trusted(event,pet))throw new Error('Unknown prototype sender');};
  ipcMain.handle('yuki:prototype-move',(event,dx,dy)=>{guard(event);if(!Number.isFinite(dx)||!Number.isFinite(dy)||Math.abs(dx)>500||Math.abs(dy)>500)throw new Error('Invalid delta');
    const [x,y]=pet.getPosition(),display=screen.getDisplayNearestPoint({x:Math.round(x+dx+128),y:Math.round(y+dy+128)}).workArea;
    pet.setPosition(Math.round(Math.max(display.x,Math.min(display.x+display.width-256,x+dx))),Math.round(Math.max(display.y,Math.min(display.y+display.height-256,y+dy))));});
  ipcMain.on('yuki:prototype-hit',(event,value)=>{guard(event);if(typeof value==='boolean')pet.setIgnoreMouseEvents(!value,{forward:true});});
  ipcMain.on('yuki:prototype-close',event=>{guard(event);app.quit();});
  pet.on('closed',()=>app.quit());
  await pet.loadURL('yuki://app/pet.html');
  if(smoke){
    for(let i=0;i<100;i++){if(await pet.webContents.executeJavaScript('document.documentElement.dataset.ready === "true"'))break;await new Promise(resolve=>setTimeout(resolve,100));}
    await new Promise(resolve=>setTimeout(resolve,250));
    const state=await pet.webContents.executeJavaScript(`(()=>{const canvas=document.querySelector('canvas'),data=canvas.getContext('2d').getImageData(0,0,256,256).data;let clear=0,solid=0;for(let i=3;i<data.length;i+=4){if(data[i]===0)clear++;if(data[i]>200)solid++;}return {ready:document.documentElement.dataset.ready,error:document.documentElement.dataset.error,clear,solid,node:typeof require};})()`);
    if(state.ready!=='true'||state.clear<1000||state.solid<1000||state.node!=='undefined')throw new Error('PNG prototype validation failed: '+JSON.stringify(state));
    const report=process.env.YUKI_SMOKE_REPORT;if(report)require('node:fs').writeFileSync(report,JSON.stringify({prototype:state,transparent:pet.isVisible()?null:true,note:'Hidden canvas test; native desktop composition still needs manual inspection'},null,2));
    console.log('PASS PNG canvas alpha and resources',JSON.stringify(state));app.quit();
  }
}
module.exports={launch};
