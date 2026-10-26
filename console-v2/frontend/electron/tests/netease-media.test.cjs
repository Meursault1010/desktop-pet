const {test}=require('node:test');
const assert=require('node:assert/strict');
const {EventEmitter}=require('node:events');
const {PassThrough}=require('node:stream');
const {neteaseMedia,selectMedia}=require('../main/netease-media.cjs');
test('NetEase track detection wins over unrelated video without inventing playing state',()=>{
 const video={available:true,status:'Playing',app:'bilibili'},native={available:true,status:'Unknown',app:'netease-uia:1:2'};
 assert.equal(selectMedia(video,native),native);
 assert.equal(selectMedia(video,{...native,status:'Paused'}),video);
 assert.equal(selectMedia({available:false},{...native,status:'Paused'}).app,native.app);
 assert.equal(selectMedia(video,{available:false}),video);
 assert.equal(selectMedia(video,null),video);
});
test('native adapter validates commands, identity and seek before launch',async()=>{
 const spawnImpl=()=>{throw Error('should not spawn');};
 for(const value of [{command:'bad'},{command:'pause',app:'bilibili'},{command:'seek',app:'netease-uia:1:2',position:NaN}])await assert.rejects(neteaseMedia(value,{spawnImpl}));
});
test('native adapter returns actual snapshot and forwards targeted arguments',async()=>{
 let args;const child=new EventEmitter();child.stdout=new PassThrough();child.kill=()=>{};
 const promise=neteaseMedia({command:'seek',app:'netease-uia:1:2',position:20,title:'Song',artist:'Artist'},{spawnImpl:(exe,a)=>{args=a;return child;}});
 child.stdout.write(JSON.stringify({ok:true,media:{available:true,position:20}}));child.emit('close',0);
 assert.equal((await promise).position,20);assert.deepEqual(args,['seek','netease-uia:1:2','20','Song','Artist']);
});
test('native adapter aborts, times out, bounds output and rejects helper errors',async()=>{
 for(const mode of ['abort','timeout','overflow','error']){
  let killed=false;const child=new EventEmitter();child.stdout=new PassThrough();child.kill=()=>{killed=true;};const controller=new AbortController();
  const promise=neteaseMedia(undefined,{spawnImpl:()=>child,signal:controller.signal,timeout:10});
  if(mode==='abort')controller.abort();if(mode==='overflow')child.stdout.write('x'.repeat(32769));if(mode==='error'){child.stdout.write('{"ok":false,"error":"Track changed"}');child.emit('close',1);}
  await assert.rejects(promise);assert.equal(killed,true);
 }
});
