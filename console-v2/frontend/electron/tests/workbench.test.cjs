'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {WorkbenchConfig}=require('../main/workbench-config.cjs');
const {validate}=require('../shared/protocol.cjs');
test('workbench config persists allowed appearance and memory without exposing arbitrary fields',()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-workbench-'));
 try{const file=path.join(dir,'workbench.json'),c=new WorkbenchConfig(file);
 c.write(c.validate({theme:'dark',memory:'喜欢茉莉花茶',shortcuts:{console:'Control+Alt+J'}}));
 assert.equal(new WorkbenchConfig(file).snapshot().memory,'喜欢茉莉花茶');
 assert.equal(c.value.shortcuts.console,'Control+Alt+J');
 assert.throws(()=>c.validate({theme:'wrong'}));assert.throws(()=>c.validate({memory:'x'.repeat(6001)}));
 assert.throws(()=>c.validate({shortcuts:{console:c.value.shortcuts.capture}}));
 assert.throws(()=>c.validate({apiKey:'secret'}));assert.throws(()=>c.validate({reduced:1}));
 const snapshot=c.snapshot();snapshot.shortcuts.console='broken';assert.notEqual(c.value.shortcuts.console,'broken');
 }finally{fs.rmSync(dir,{recursive:true,force:true});}
});
test('UI, corner placement and temporary focus use bounded sidecar commands',()=>{
 assert.doesNotThrow(()=>validate('set_focus',{enabled:true}));
 assert.throws(()=>validate('set_focus',{enabled:'true'}));assert.throws(()=>validate('set_focus',{enabled:true,quiet:true}));
 assert.doesNotThrow(()=>validate('go_corner',{}));assert.throws(()=>validate('go_corner',{x:10}));
 assert.doesNotThrow(()=>validate('configure_ui',{theme:'mist',bubble:'light',reduced:true,translation:false}));
 assert.throws(()=>validate('configure_ui',{theme:'mist',bubble:'light',reduced:true,translation:'false'}));
});
