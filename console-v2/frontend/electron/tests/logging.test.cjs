const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {Writable}=require('node:stream');
const {fork}=require('node:child_process');
const {once}=require('node:events');
const {createMainLogger}=require('../main/logging.cjs');

function setup(t,options={}){
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-log-test-'));
  t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const file=path.join(folder,'logs/yuki.log');
  const stdout=new Writable({write(_chunk,_encoding,done){done();}});
  const stderr=new Writable({write(_chunk,_encoding,done){done();}});
  const logger=createMainLogger({file,stdout,stderr,...options});
  t.after(()=>logger.dispose());
  return {file,stdout,stderr,logger};
}

test('GUI logs survive unavailable terminals and retain the original IPC error',t=>{
  let writes=0;
  const terminal=new Writable({write(_chunk,_encoding,done){writes++;done(new Error('unavailable'));}});
  const {file,logger}=setup(t,{stdout:terminal,stderr:terminal});
  logger.console.error('Error occurred in handler for yuki:request:',new Error('宠物尚未连接'));
  logger.console.log('still responsive');
  assert.equal(writes,0);
  assert.match(fs.readFileSync(file,'utf8'),/宠物尚未连接/);
  assert.match(fs.readFileSync(file,'utf8'),/still responsive/);
});

test('asynchronous EPIPE during mirrored diagnostics does not crash or retry the pipe',async t=>{
  let writes=0;
  const terminal=new Writable({write(_chunk,_encoding,done){
    writes++;setImmediate(()=>done(Object.assign(new Error('broken pipe'),{code:'EPIPE'})));
  }});
  const {file,logger}=setup(t,{mirror:true,stderr:terminal});
  logger.console.error('original request rejection');
  await new Promise(resolve=>terminal.once('error',resolve));
  logger.console.error('subsequent request rejection');
  assert.equal(writes,1);
  const text=fs.readFileSync(file,'utf8');
  assert.match(text,/original request rejection/);
  assert.match(text,/terminal pipe closed \(EPIPE\)/);
  assert.match(text,/subsequent request rejection/);
});

test('unrelated stream errors are not silently suppressed',t=>{
  const {stdout}=setup(t);
  const failure=Object.assign(new Error('unexpected failure'),{code:'ENOSPC'});
  assert.throws(()=>stdout.emit('error',failure),error=>error===failure);
});

test('a real child keeps working after its parent closes stdout and stderr',async t=>{
  const folder=fs.mkdtempSync(path.join(os.tmpdir(),'yuki-closed-pipes-'));
  t.after(()=>fs.rmSync(folder,{recursive:true,force:true}));
  const file=path.join(folder,'yuki.log');
  const child=fork(path.join(__dirname,'logging-fixture.cjs'),[file],{stdio:['ignore','pipe','pipe','ipc']});
  t.after(()=>{if(child.exitCode===null)child.kill();});
  const exit=once(child,'exit');
  const [ready]=await once(child,'message');
  assert.equal(ready,'ready');
  child.stdout.destroy();child.stderr.destroy();
  child.send('write');
  const [code,signal]=await exit;
  assert.equal(signal,null);
  assert.equal(code,0);
  const text=fs.readFileSync(file,'utf8');
  assert.match(text,/original IPC rejection/);
  assert.match(text,/EPIPE/);
  assert.match(text,/after pipe closure/);
});
