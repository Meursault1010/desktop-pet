'use strict';
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
if(process.env.YUKI_OCR_APP)process.resourcesPath=path.join(process.env.YUKI_OCR_APP,'resources');
const modules=process.env.YUKI_OCR_APP?path.join(process.env.YUKI_OCR_APP,'resources/app/electron/main'):path.join(root,'console-v2/frontend/electron/main');
const {LocalOCR}=require(path.join(modules,'ocr.cjs'));
const {Attachments}=require(path.join(modules,'attachments.cjs'));
const {Assistant}=require(path.join(modules,'assistant.cjs'));
async function main(){
 const folder=path.join(root,'docs/验收资料/ocr-20261020');
 const executable=process.env.YUKI_OCR_APP?path.join(process.env.YUKI_OCR_APP,'resources/ocr/yuki-ocr.exe'):path.join(root,'.electron-build/ocr-dist/yuki-ocr/yuki-ocr.exe');
 const ocr=new LocalOCR({getCommand:()=>[executable,[]]});
 const a=new Attachments({ocr});const started=Date.now();
 const file=await a.add(path.join(folder,'text-sample.png'),{imageReader:async b=>'data:image/png;base64,'+b.toString('base64')});
 const elapsed=Date.now()-started;const extracted=a.resolve([file.id])[0].text;
 assert.match(extracted,/403/);assert.match(extracted,/访问/);assert.match(extracted,/Hello Yuki/i);assert.match(extracted,/download is complete/i);
 const transparent=await a.add(path.join(folder,'transparent-text.png'),{imageReader:async b=>'data:image/png;base64,'+b.toString('base64')});
 assert.match(a.resolve([transparent.id])[0].text,/Yuki/);
 await assert.rejects(a.add(path.join(folder,'blank.png'),{imageReader:async()=> 'data:image/png;base64,blank'}),/没有识别到文字/);
 const bot=new Assistant();bot.attachments=a;
 const discovered=await bot.models();const model=discovered.models.find(x=>x==='qwen3.8-4b-distill');assert.ok(model,'Current Qwen must be available');
 const response=await bot.chat({id:'ocr-live-validation',model,messages:[{role:'user',content:'请只将图片中最后一句英文翻译成中文。',attachments:[file.id]}]},()=>{});
 assert.match(response.text,/下载/);assert.match(response.text,/完成/);
 const report={passed:true,executable,ocrMs:elapsed,extracted,endpoint:bot.endpoint,model,answer:response.text,blankRejected:true,transparentImagePassed:true,packaged:!!process.env.YUKI_OCR_APP};
 fs.writeFileSync(path.join(folder,process.env.YUKI_OCR_APP?'packaged-verification.json':'verification.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
