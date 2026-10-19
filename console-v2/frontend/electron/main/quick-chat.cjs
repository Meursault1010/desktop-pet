'use strict';

class QuickChat {
  constructor(assistant,deliver){this.assistant=assistant;this.deliver=deliver;this.history=[];this.busy=false;this.generation=0;}
  async run(id,text){
    if(typeof id!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(id)||typeof text!=='string'||!text.trim()||text.length>2000)return;
    const generation=this.generation;
    const post=(phase,value)=>generation===this.generation?this.deliver({id,phase,text:value.slice(0,6000)}):Promise.resolve();
    if(this.busy||this.assistant.active){await post('error','我正在回复另一条消息，等我说完再聊，好吗？');return;}
    this.busy=true;
    try{
      await post('thinking','让我想一想…');
      const {models}=await this.assistant.models();
      if(generation!==this.generation)return;
      const model=models.includes(this.assistant.preferredModel)?this.assistant.preferredModel:
        models.find(name=>/qwen3[._-]?8[-_ ]?4b/i.test(name))||models[0];
      if(!model)throw new Error('本地服务已连接，请先在 LM Studio 加载聊天模型。');
      let history=[...this.history,{role:'user',content:text.trim()}].slice(-10);
      while(history.length>1&&history.reduce((n,m)=>n+m.content.length,0)>3800)history=history.slice(1);
      let last=0,delivery=Promise.resolve();
      const result=await this.assistant.chat({id,model,messages:history},update=>{
        if(update.phase==='answer'&&Date.now()-last>160){
          last=Date.now();
          // Serial delivery prevents an older streaming frame overwriting done.
          delivery=delivery.then(()=>post('answer',update.text)).catch(()=>{});
        }
      });
      await delivery;
      if(generation!==this.generation)return;
      this.history=[...history,{role:'assistant',content:result.text}].slice(-10);
      await post('done',result.text);
    }catch(error){await post('error',String(error.message||error).slice(0,1000));}
    finally{this.busy=false;}
  }
  cancel(){this.generation++;if(this.busy)this.assistant.cancel();this.history=[];}
}
module.exports={QuickChat};
