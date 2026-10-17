import {test} from 'node:test';
import assert from 'node:assert/strict';
import {frameAt} from '../src/pet/timeline.ts';
import {PngRenderer} from '../src/pet/PngRenderer.ts';

test('PNG timeline plays intro once and preserves screen loopStart',()=>{
  assert.deepEqual(frameAt(0,[10,20,30],true,1),{index:0,done:false});
  assert.equal(frameAt(60,[10,20,30],true,1).index,1);
  assert.equal(frameAt(110,[10,20,30],true,1).index,1);
  assert.deepEqual(frameAt(61,[10,20,30],false),{index:2,done:true});
  assert.throws(()=>frameAt(0,[10,0],true));assert.throws(()=>frameAt(0,[10],true,1));
});
test('PNG renderer validates loaded atlas cells and rejects missing/external assets',async()=>{
  const originals={Image:globalThis.Image,requestAnimationFrame:globalThis.requestAnimationFrame,cancelAnimationFrame:globalThis.cancelAnimationFrame};
  let tick,cleared=0,cancelled=false;
  globalThis.requestAnimationFrame=callback=>{tick=callback;return 1;};globalThis.cancelAnimationFrame=()=>{cancelled=true;};
  globalThis.Image=class {width=2048;height=2048;set src(url){this.url=url;queueMicrotask(()=>url.includes('missing')?this.onerror():this.onload());}};
  const context={clearRect(){cleared++;},drawImage(){},imageSmoothingEnabled:true,globalAlpha:1};
  const canvas={getContext:()=>context,width:256,height:256};const renderer=new PngRenderer(canvas);
  try{
    await renderer.loadCharacter('yuki');tick(performance.now());assert.equal(context.imageSmoothingEnabled,false);
    const clip={id:'screen',atlas:'actions/screen/atlas.png',frames:12,columns:4,cell:256,durations:Array(12).fill(100),loop_start:5};
    await renderer.playAction(clip,true);tick(performance.now());
    await assert.rejects(renderer.playAction({...clip,atlas:'missing.png'}),/加载失败/);
    await assert.rejects(renderer.playAction({...clip,frames:100,durations:Array(100).fill(10)}),/缺帧/);
    await assert.rejects(renderer.playAction({...clip,cell:64}),/定义无效/);
    await renderer.stopAction();assert.throws(()=>renderer.setParameter('scale',NaN));
  }finally{renderer.dispose();Object.assign(globalThis,originals);}
  assert.ok(cleared>1);assert.ok(cancelled);
});
