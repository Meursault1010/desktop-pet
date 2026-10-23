'use strict';
const {spawn}=require('node:child_process');
const path=require('node:path');
const fs=require('node:fs');
const assert=require('node:assert/strict');
const root=path.resolve(__dirname,'../..');
const {query}=require(path.join(root,'console-v2/frontend/electron/main/selection.cjs'));
async function main(){
 const fixture=spawn(path.join(root,'.electron-build/selection-test.exe'),[],{windowsHide:false,stdio:['pipe','pipe','ignore']});
 try{
  fixture.stdout.setEncoding('utf8');let buffer='';
  const value=await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>reject(Error('fixture timeout')),5000);fixture.on('error',reject);fixture.stdout.on('data',chunk=>{buffer+=chunk;if(buffer.includes('\n')){clearTimeout(timeout);resolve(JSON.parse(buffer.trim()));}});});
  assert.equal(value.foreground,value.hwnd,'test fixture must own foreground before querying');
  const exe=path.join(root,'.electron-build/selection/yuki-selection.exe');
  const uia=await query(exe,['uia',value.hwnd,String(value.x),String(value.y)],2500);
  console.log('UIA',uia);assert.match(uia.text,/Hello Yuki/);
  const copy=await query(exe,['copy',value.hwnd],2500);assert.match(copy.text,/download is complete/);
  const report={passed:true,uia:uia.text,copy:copy.text,clipboardRestored:copy.restored};assert.equal(copy.restored,true);
  const dir=path.join(root,'docs/验收资料/translation-20261020');fs.mkdirSync(dir,{recursive:true});fs.writeFileSync(path.join(dir,'native-selection.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
 }finally{fixture.stdin.end('\n');}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
