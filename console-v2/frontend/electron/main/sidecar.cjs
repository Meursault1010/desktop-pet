'use strict';
const {EventEmitter} = require('node:events');
const {spawn} = require('node:child_process');
const {StringDecoder} = require('node:string_decoder');
const {validate,validateMessage,MAX_LINE,MAX_REQUEST} = require('../shared/protocol.cjs');

class Sidecar extends EventEmitter {
  constructor({command,args=[],cwd,env={},spawnProcess=spawn,timeout=6000,readyTimeout=15000,maxPending=32}) {
    super(); Object.assign(this,{command,args,cwd,env,spawnProcess,timeout,readyTimeout,maxPending});
    this.child=null; this.pending=new Map(); this.counter=0; this.ready=false; this.stopping=false;
    this.starting=null; this.lastStart=0;
  }
  start() {
    if (this.ready) return Promise.resolve();
    if (this.starting) return this.starting;
    if (this.child) return Promise.reject(new Error('后端正在退出，请稍后重连'));
    if (Date.now()-this.lastStart<500) return Promise.reject(new Error('请稍后再重连'));
    this.lastStart=Date.now(); this.stopping=false;
    this.starting=new Promise((resolve,reject)=>{this.resolveReady=resolve;this.rejectReady=reject;});
    const starting=this.starting;
    try {
      const child=this.spawnProcess(this.command,this.args,{cwd:this.cwd,windowsHide:true,
        env:{...process.env,...this.env,PYTHONIOENCODING:'utf-8',PYTHONDONTWRITEBYTECODE:'1'},stdio:['pipe','pipe','pipe']});
      this.child=child;
      let buffer=''; const decoder=new StringDecoder('utf8');
      child.stdout.on('data',chunk=>{
        if (this.child!==child) return;
        buffer+=decoder.write(chunk);
        let newline;
        while ((newline=buffer.indexOf('\n'))>=0) {
          const line=buffer.slice(0,newline); buffer=buffer.slice(newline+1);
          if (Buffer.byteLength(line)>MAX_LINE) {this.fail(new Error('后端消息过大'));child.kill();return;}
          try {this.message(validateMessage(JSON.parse(line)));}
          catch(error) {this.fail(error);child.kill();return;}
        }
        if (Buffer.byteLength(buffer)>MAX_LINE) {this.fail(new Error('后端消息过大'));child.kill();}
      });
      child.stderr.on('data',chunk=>this.emit('log',chunk.toString('utf8').slice(0,8192)));
      child.stdin.on('error',error=>this.fail(error));
      child.once('error',error=>{this.fail(new Error(`宠物启动失败：${error.message}`));});
      child.once('close',(code,signal)=>{
        if (this.child!==child) return;
        this.child=null;this.ready=false;
        this.fail(new Error(this.stopping?'宠物已退出':`宠物连接已断开（${code??signal}）`));
        this.emit('disconnected',this.stopping?'宠物已退出':'宠物连接已断开，可重新连接');
      });
      this.readyTimer=setTimeout(()=>{this.fail(new Error('宠物启动超时'));child.kill();},this.readyTimeout);
    } catch(error) {this.child=null;this.fail(error);}
    return starting;
  }
  fail(error) {
    clearTimeout(this.readyTimer);this.ready=false;
    this.rejectReady?.(error);this.resolveReady=null;this.rejectReady=null;this.starting=null;
    for (const {reject,timer} of this.pending.values()) {clearTimeout(timer);reject(error);}
    this.pending.clear();
  }
  message(message) {
    if (message.type==='ready') {
      clearTimeout(this.readyTimer);this.ready=true;this.resolveReady?.();
      this.resolveReady=null;this.rejectReady=null;this.starting=null;
    }
    if (message.type==='response') {
      const item=this.pending.get(message.id);
      if (item) {clearTimeout(item.timer);this.pending.delete(message.id);
        if (message.ok) item.resolve(message);else item.reject(new Error(message.error||'操作失败'));}
    }
    this.emit('message',message);
  }
  async request(name,payload={}) {
    validate(name,payload);
    if (!this.ready || !this.child || this.child.stdin.destroyed) throw new Error('宠物尚未连接');
    if (this.pending.size>=this.maxPending) throw new Error('操作队列已满');
    const id=String(++this.counter),line=JSON.stringify({id,name,payload})+'\n';
    if (Buffer.byteLength(line)>MAX_REQUEST) throw new Error('请求过大');
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error('操作超时，请检查宠物状态'));},this.timeout);
      this.pending.set(id,{resolve,reject,timer});
      this.child.stdin.write(line,'utf8',error=>{if(error){const p=this.pending.get(id);if(p){clearTimeout(p.timer);this.pending.delete(id);p.reject(error);}}});
    });
  }
  async stop() {
    this.stopping=true;
    const child=this.child;if(!child)return;
    const closed=new Promise(resolve=>child.once('close',resolve));
    try {if(this.ready)await this.request('shutdown');}catch{}
    child.stdin.end();
    let timer;
    await Promise.race([closed,new Promise(resolve=>{timer=setTimeout(()=>{child.kill();resolve();},2500);})]);
    clearTimeout(timer);
    if(this.child===child && child.exitCode===null) {
      await Promise.race([closed,new Promise(resolve=>setTimeout(resolve,1000))]);
    }
    this.fail(new Error('宠物已退出'));
  }
}
module.exports={Sidecar};
