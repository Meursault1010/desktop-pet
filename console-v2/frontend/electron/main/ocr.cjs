'use strict';
const path=require('node:path');
const fs=require('node:fs');
const {spawn}=require('node:child_process');

function command(){
 const project=path.resolve(__dirname,'../../../..');
 const executable=path.join(process.resourcesPath||path.join(project,'.electron-build'),'ocr','yuki-ocr.exe');
 if(fs.existsSync(executable))return [executable,[]];
 const python=path.join(project,'.electron-build/ocr-venv/Scripts/python.exe');
 if(fs.existsSync(python))return [python,[path.join(project,'tools/ocr/worker.py')]];
 throw Error('本地 OCR 未安装，请先运行 build-ocr.ps1 并重新打包');
}
class LocalOCR {
 constructor({launch=spawn,getCommand=command,timeout=90000}={}){this.launch=launch;this.getCommand=getCommand;this.timeout=timeout;this.busy=false;}
 async recognize(buffer){
  if(this.busy)throw Error('正在识别另一张图片，请稍候');
  this.busy=true;
  try{
   const [exe,args]=this.getCommand();
   return await new Promise((resolve,reject)=>{
    const child=this.launch(exe,args,{windowsHide:true,stdio:['pipe','pipe','pipe']});
    let output='',size=0,settled=false;
    const finish=(error,result)=>{if(settled)return;settled=true;clearTimeout(timer);if(error)reject(error);else resolve(result);};
    const timer=setTimeout(()=>{child.kill();finish(Error('图片文字识别超时，请尝试裁剪图片'));},this.timeout);
    child.on('error',()=>finish(Error('无法启动本地 OCR')));
    child.stdin.on('error',()=>finish(Error('本地 OCR 输入失败')));
    child.stdout.on('data',chunk=>{size+=chunk.length;if(size>1024*1024){child.kill();finish(Error('OCR 输出过大'));}else output+=chunk.toString('utf8');});
    child.stderr.resume();
    child.on('close',code=>{
     if(settled)return;
     try{
      const result=JSON.parse(output.trim().split(/\r?\n/).at(-1));
      if(code!==0||result.error||typeof result.text!=='string')throw Error();
      if(!result.text.trim())return finish(Error('没有识别到文字，请使用清晰的文字截图；当前模式不能识别物品或场景'));
      finish(null,{text:result.text.slice(0,18000),truncated:!!result.truncated,lines:result.lines});
     }catch{finish(Error('本地 OCR 识别失败，请尝试其他图片'));}
    });
    child.stdin.end(JSON.stringify({image:buffer.toString('base64')}));
   });
  }finally{this.busy=false;}
 }
}
module.exports={LocalOCR};
