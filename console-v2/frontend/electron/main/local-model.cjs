'use strict';
const fs=require('node:fs');
const path=require('node:path');
const net=require('node:net');
const {spawn}=require('node:child_process');
const ENDPOINT='http://127.0.0.1:1236/v1';
const MODEL='qwen3.8-4b-distill';
class LocalModel {
  constructor({root,log=()=>{},fetchImpl=fetch,spawnProcess=spawn}){
    Object.assign(this,{root,log,fetch:fetchImpl,spawnProcess});this.child=null;this.starting=null;this.stopped=false;
  }
  get available(){return fs.existsSync(path.join(this.root,'runtime/llama-server.exe'))&&fs.existsSync(path.join(this.root,'Qwen3.8-4B-Q4_K_M.gguf'));}
  async ready(){
    try{const r=await this.fetch(ENDPOINT+'/models',{signal:AbortSignal.timeout(1500),redirect:'error'});if(!r.ok)return false;const data=await r.json();return data.data?.some(x=>x.id===MODEL)===true;}catch{return false;}
  }
  ensure(){
    if(this.stopped)return Promise.reject(Error('本地模型已停止'));
    if(this.starting)return this.starting;
    this.starting=this.start().finally(()=>{this.starting=null;});return this.starting;
  }
  async start(){
    if(await this.ready())return;
    if(!this.available)throw Error('项目内的 Qwen 模型或推理运行库缺失，请恢复 local-model/qwen 目录。');
    if(this.stopped)throw Error('本地模型已停止');
    if(!this.child){
      await new Promise((resolve,reject)=>{const server=net.createServer();server.once('error',()=>reject(Error('本地模型端口 1236 被占用，请关闭占用该端口的程序后重试。')));server.listen(1236,'127.0.0.1',()=>server.close(resolve));});
      if(this.stopped)throw Error('本地模型已停止');
      const child=this.spawnProcess(path.join(this.root,'runtime/llama-server.exe'),[
        '-m',path.join(this.root,'Qwen3.8-4B-Q4_K_M.gguf'),'--alias',MODEL,
        '--host','127.0.0.1','--port','1236','-c','8192','-np','1','-ngl','99','--reasoning','off'
      ],{cwd:this.root,windowsHide:true,stdio:['ignore','ignore','pipe']});
      this.child=child;this.failure=null;
      child.stderr.on('data',data=>this.log('[Qwen] '+data.toString().slice(-2000)));
      child.once('error',error=>{this.failure=error;});
      child.once('close',code=>{if(this.child===child)this.child=null;this.failure=this.failure||Error('Qwen 进程已退出（'+code+'），请查看 Yuki 日志。');});
    }
    const deadline=Date.now()+120000;
    while(Date.now()<deadline){
      if(this.stopped)throw Error('本地模型已停止');
      if(this.failure)throw this.failure;
      if(await this.ready()){this.log('项目内 Qwen 已就绪');return;}
      await new Promise(resolve=>setTimeout(resolve,500));
    }
    this.child?.kill();throw Error('Qwen 加载超时，请检查可用内存后重试。');
  }
  async resume(){
    // A canceled startup must settle before another launch can begin.
    if(this.starting)await this.starting.catch(()=>{});
    this.stopped=false;return this.ensure();
  }
  async stop(){
    this.stopped=true;
    const child=this.child;if(!child)return;
    await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Model process did not exit; retry disabling.')),5000);child.once('close',()=>{clearTimeout(timer);resolve();});child.kill();});
  }
}
module.exports={LocalModel,ENDPOINT,MODEL};
