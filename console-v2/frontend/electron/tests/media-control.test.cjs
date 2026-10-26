const {test}=require('node:test');
const assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {PassThrough}=require('node:stream');
const {controlMedia}=require('../main/media-control.cjs');
function worker(){const child=new EventEmitter();child.stdout=new PassThrough();child.stderr=new PassThrough();child.kill=()=>{child.killed=true;};return child;}
const value={command:'pause',app:'Test Player'};
test('seek uses a bounded numeric position and passes it as a separate argument',async()=>{
 for(const position of [-1,NaN,Infinity,'30',undefined])await assert.rejects(controlMedia({...value,command:'seek',position},{platform:'win32'}),/进度/);
 const child=worker();const p=controlMedia({...value,command:'seek',position:42.5,title:'Song',artist:'Artist'},{platform:'win32',spawnImpl:(_exe,args)=>{assert.deepEqual(args.slice(-2),['-Position','42.5']);return child;}});
 child.stdout.write(JSON.stringify({ok:true,media:{available:true,position:42.5}}));child.emit('close',0);assert.equal((await p).position,42.5);
});
test('only fixed commands on Windows are accepted before spawning',async()=>{
 let spawned=false;const options={spawnImpl:()=>{spawned=true;},platform:'win32'};
 for(const v of [null,{}, {...value,command:'toggle'}, {...value,app:''}])await assert.rejects(controlMedia(v,options),/参数无效/);
 await assert.rejects(controlMedia(value,{...options,platform:'linux'}),/Windows/);assert.equal(spawned,false);
});
test('passes arguments without shell expansion and returns actual session data',async()=>{
 const child=worker();const media={available:true,status:'Paused'};
 const pending=controlMedia(value,{platform:'win32',spawnImpl:(exe,args,options)=>{assert.equal(exe,'powershell.exe');assert.equal(args.at(-1),value.app);assert.equal(args.at(-3),value.command);assert.equal(options.shell,undefined);return child;}});
 child.stdout.write(JSON.stringify({ok:true,media}));child.emit('close',0);assert.deepEqual(await pending,media);
});
test('false operation, malformed output, and launch failure reject honestly',async()=>{
 for(const response of [JSON.stringify({ok:false,error:'播放器未接受操作'}),'invalid',JSON.stringify({ok:true})]){
  const child=worker();const p=controlMedia(value,{platform:'win32',spawnImpl:()=>child});child.stdout.write(response);child.emit('close',0);await assert.rejects(p,/播放器/);assert.equal(child.killed,true);
 }
 const child=worker();const p=controlMedia(value,{platform:'win32',spawnImpl:()=>child});child.emit('error',new Error('ENOENT'));await assert.rejects(p,/无法启动/);
});
test('timeout, oversized response and shutdown cancel and kill the helper',async()=>{
 const child=worker();await assert.rejects(controlMedia(value,{platform:'win32',spawnImpl:()=>child,timeout:10}),/超时/);assert.equal(child.killed,true);
 const large=worker();const p=controlMedia(value,{platform:'win32',spawnImpl:()=>large});large.stdout.write('x'.repeat(32769));await assert.rejects(p,/数据异常/);assert.equal(large.killed,true);
 const cancelled=worker(),controller=new AbortController();const q=controlMedia(value,{platform:'win32',spawnImpl:()=>cancelled,signal:controller.signal});controller.abort();await assert.rejects(q,/取消/);assert.equal(cancelled.killed,true);
});
