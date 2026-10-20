'use strict';
const fs=require('node:fs');
const path=require('node:path');
const {Console}=require('node:console');
const {Writable}=require('node:stream');

// A GUI may outlive the shell that launched it. Electron itself calls
// console.error when an IPC handler rejects, even if our code never logs there.
// Keep the diagnostic in a file; a lost terminal must not become a second crash.
function createMainLogger({file,mirror=false,stdout=process.stdout,stderr=process.stderr}){
  const append=(message)=>{
    try{
      fs.mkdirSync(path.dirname(file),{recursive:true});
      fs.appendFileSync(file,`${new Date().toISOString()} ${String(message).slice(0,8192)}\n`);
    }catch{/* Logging failure must not replace the original operation's error. */}
  };
  const guards=[];
  const sink=(name,terminal)=>{
    let connected=true;
    const disconnected=error=>{
      // Do not suppress unrelated stream failures or general app exceptions.
      if(error.code!=='EPIPE')throw error;
      if(connected){connected=false;append(`[${name}] terminal pipe closed (EPIPE)`);}
    };
    terminal.on('error',disconnected);
    guards.push(()=>terminal.removeListener('error',disconnected));
    return new Writable({write(chunk,_encoding,done){
      append(`[${name}] ${chunk.toString('utf8').trimEnd()}`);
      if(mirror&&connected&&!terminal.destroyed&&!terminal.writableEnded){
        try{terminal.write(chunk);}catch(error){disconnected(error);}
      }
      done();
    }});
  };
  const output=sink('stdout',stdout),errors=sink('stderr',stderr);
  return {console:new Console({stdout:output,stderr:errors,ignoreErrors:false}),
    log:message=>append(message instanceof Error?message.stack||message.message:message),
    dispose:()=>{for(const remove of guards)remove();output.end();errors.end();}};
}
module.exports={createMainLogger};
