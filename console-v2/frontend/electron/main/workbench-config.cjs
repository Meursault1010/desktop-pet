'use strict';
const fs=require('node:fs');
const path=require('node:path');
const defaults={theme:'mist',bubble:'mist',reduced:false,particles:true,buttonHints:true,persona:'',memory:'',shortcuts:{console:'Control+Alt+Y',visibility:'Control+Alt+H',translation:'Control+Alt+T',capture:'Control+Alt+O'}};
class WorkbenchConfig{
 constructor(file){this.file=file;this.value=structuredClone(defaults);try{this.value=this.validate(JSON.parse(fs.readFileSync(file,'utf8')));}catch{}}
 snapshot(){return structuredClone(this.value);}
 validate(input){
  if(!input||typeof input!=='object'||Array.isArray(input)||Object.keys(input).some(k=>!Object.hasOwn(defaults,k)))throw Error('工作台设置无效');
  const v={...this.value,...input,shortcuts:{...this.value.shortcuts,...input.shortcuts}};
  if(!['light','mist','dark'].includes(v.theme)||!['light','mist','dark'].includes(v.bubble)||typeof v.reduced!=='boolean'||typeof v.particles!=='boolean'||typeof v.buttonHints!=='boolean')throw Error('主题设置无效');
  if(typeof v.persona!=='string'||v.persona.length>3000||typeof v.memory!=='string'||v.memory.length>6000)throw Error('人设或记忆内容过长');
  if(!v.shortcuts||Object.keys(v.shortcuts).some(k=>!Object.hasOwn(defaults.shortcuts,k))||Object.values(v.shortcuts).some(s=>typeof s!=='string'||s.length>80||!s.includes('+')||!/(Control|Alt)/.test(s)))throw Error('快捷键需要包含 Ctrl 或 Alt');
  const values=Object.values(v.shortcuts);if(new Set(values.map(s=>s.toLowerCase())).size!==values.length)throw Error('快捷键不能重复');return v;
 }
 write(value){fs.mkdirSync(path.dirname(this.file),{recursive:true});const temp=this.file+'.tmp';fs.writeFileSync(temp,JSON.stringify(value,null,2),'utf8');fs.renameSync(temp,this.file);this.value=value;return this.snapshot();}
}
module.exports={WorkbenchConfig,defaults};
