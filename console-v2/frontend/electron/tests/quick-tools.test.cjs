const {test}=require('node:test');
const assert=require('node:assert/strict');
const {QuickTools,project,validateAction}=require('../main/quick-tools.cjs');
const focus={end:null,remaining:1500,duration:25,mode:'focus',completed:0};
test('native popup projects bounded previews and forwards shared tool changes',async()=>{
 const deliveries=[],actions=[],forward=[];
 const desktop={snapshot:()=>({clipboard:[{id:'clip',text:'文'.repeat(600),at:1}],clipboardPaused:false}),action:async v=>actions.push(v)};
 const q=new QuickTools({desktop,deliver:v=>deliveries.push(v),forward:v=>forward.push(v)});
 await q.sync({focus,todos:[{id:'todo',text:'任务',done:false,due:''}]});
 assert.equal(deliveries.at(-1).clipboard[0].text.length,240);
 await q.action('clipboard-copy','clip');assert.deepEqual(actions,[{name:'clipboard-copy',value:'clip'}]);
 await q.action('focus-toggle',null);assert.deepEqual(forward,[{name:'focus-toggle',value:null}]);
 await q.action('todo-add',{text:'喝水',minutes:30});assert.equal(forward.at(-1).name,'todo-add');
 await q.action('exec','anything');assert.match(deliveries.at(-1).error,/无效/);
});
test('popup sorts upcoming todos, limits five and reports unavailable workbench',async()=>{
 const todos=Array.from({length:8},(_,i)=>({id:String(i),text:'任务',done:false,due:new Date(2000000000000-i*60000).toISOString()}));
 const p=project({clipboard:[],clipboardPaused:false},{focus,todos});assert.equal(p.todos.length,5);assert.equal(p.todos[0].id,'7');assert.equal(p.todoCount,8);
 const delivered=[];const q=new QuickTools({desktop:{snapshot:()=>({clipboard:[],clipboardPaused:false})},deliver:v=>delivered.push(v),forward:()=>assert.fail()});
 await q.action('focus-toggle');assert.match(delivered.at(-1).error,/连接/);
 assert.throws(()=>validateAction('todo-add',{text:'a',minutes:9}));
});
