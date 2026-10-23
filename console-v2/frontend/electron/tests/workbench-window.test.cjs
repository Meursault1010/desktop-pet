const {test}=require('node:test');
const assert=require('node:assert/strict');
const {fitBounds,setWindowMode}=require('../main/workbench-window.cjs');
test('workbench bounds fit small and offset monitors',()=>{
 assert.deepEqual(fitBounds({x:4000,y:-900,width:1200,height:900},{x:-800,y:0,width:800,height:600}),{x:-800,y:0,width:800,height:600});
 assert.deepEqual(fitBounds({x:0,y:0,width:1,height:1},{x:0,y:0,width:1920,height:1080}),{x:0,y:0,width:520,height:420});
});
test('compact and expanded windows remember independently resized bounds',()=>{
 let bounds={x:100,y:100,width:780,height:600};
 const win={getBounds:()=>({...bounds}),isMaximized:()=>false,setBounds:b=>{bounds={...b};}};
 const screen={getDisplayMatching:()=>({workArea:{x:0,y:0,width:1920,height:1080}})};
 setWindowMode(win,screen,true);bounds={x:200,y:150,width:1300,height:850};
 setWindowMode(win,screen,false);assert.equal(bounds.width,780);
 bounds={x:100,y:100,width:600,height:500};setWindowMode(win,screen,true);assert.equal(bounds.width,1300);
 setWindowMode(win,screen,false);assert.equal(bounds.width,600);
});
