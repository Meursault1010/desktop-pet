'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {TranslationWindows}=require('../main/translation-windows.cjs');
function setup(){
 const handlers=new Map(),area={x:0,y:0,width:1920,height:1080};let bounds={x:200,y:160,width:420,height:360};
 const windows=new TranslationWindows({ipcMain:{handle:(name,callback)=>handlers.set(name,callback)},screen:{getDisplayNearestPoint:()=>({workArea:area})},translation:{cancel(){}}});
 windows.guard=()=>{};
 windows.popup={getBounds:()=>({...bounds}),setPosition:(x,y)=>{bounds={...bounds,x,y};},setSize:(width,height)=>{bounds={...bounds,width,height};},hide(){}};
 return {windows,gesture:input=>handlers.get('yuki:translation-gesture')({},input),bounds:()=>({...bounds})};
}
test('quick queued window drag uses event coordinates and keeps the title reachable',()=>{
 const {gesture,bounds}=setup();
 gesture({phase:'start',kind:'move',x:300,y:200});gesture({phase:'update',x:450,y:260});gesture({phase:'end'});
 assert.deepEqual(bounds(),{x:350,y:220,width:420,height:360});
 gesture({phase:'start',kind:'move',x:450,y:260});gesture({phase:'update',x:-9000,y:-9000});gesture({phase:'end'});
 assert.equal(bounds().x,-356);assert.equal(bounds().y,0);
});
test('resize preserves the top-left, enforces minimum size and remembers the chosen size',()=>{
 const {windows,gesture,bounds}=setup();
 gesture({phase:'start',kind:'resize',x:600,y:500});gesture({phase:'update',x:900,y:680});gesture({phase:'end'});
 assert.deepEqual(bounds(),{x:200,y:160,width:720,height:540});assert.deepEqual(windows.popupSize,{width:720,height:540});
 gesture({phase:'start',kind:'resize',x:900,y:680});gesture({phase:'update',x:-500,y:-500});gesture({phase:'end'});
 assert.deepEqual(bounds(),{x:200,y:160,width:320,height:240});
 windows.dismiss();gesture({phase:'update',x:9999,y:9999});assert.equal(bounds().width,320);
});
test('window gesture rejects malformed coordinates and unauthorized bounds fields',()=>{
 const {gesture}=setup();
 for(const input of [null,{phase:'start',kind:'exec',x:0,y:0},{phase:'update',x:Infinity,y:0},{phase:'update',x:'10',y:0},{phase:'start',kind:'move',x:0,y:0,width:9999}])assert.throws(()=>gesture(input),/窗口/);
});
test('outside clicks dismiss completed inactive popups using logical screen coordinates',()=>{
 const {windows}=setup();let phase='loading',closed=0;
 windows.translation.snapshot=()=>({phase});
 windows.screen.screenToDipPoint=({x,y})=>({x:x/2,y:y/2});
 Object.assign(windows.popup,{isDestroyed:()=>false,isVisible:()=>true,hide:()=>{closed++;}});
 windows.dismissOutside({x:200,y:200});assert.equal(closed,0);
 phase='done';
 windows.dismissOutside({x:600,y:400});assert.equal(closed,0);
 windows.gesture={kind:'move'};
 windows.dismissOutside({x:200,y:200});assert.equal(closed,0);
 windows.gesture=null;
 windows.dismissOutside({x:200,y:200});assert.equal(closed,1);
});
