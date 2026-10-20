'use strict';
const fs=require('node:fs');
const path=require('node:path');
const schedulePath=[path.join(__dirname,'../../../assets/daily-routine.json'),
  path.join(process.resourcesPath||'','pet/assets/daily-routine.json')].find(p=>fs.existsSync(p));
const routineSchedule=JSON.parse(fs.readFileSync(schedulePath,'utf8'));
function routineContext(at=new Date()){
  const period=[...routineSchedule].reverse().find(p=>at.getHours()>=p.start);
  const clock=String(at.getHours()).padStart(2,'0')+':'+String(at.getMinutes()).padStart(2,'0');
  return `当前用户设备本地时间 ${clock}，你的生活阶段是「${period.name}」。让语气自然贴合时段，夜间可以轻声、带一点困意，但仍然乐意回应用户。日程是状态倾向，不代表你已完成进食、洗漱或睡眠，不据此推断用户正在做什么。不要每次回复都报时或重复日程。`;
}
const ENDPOINT='http://127.0.0.1:1235/v1';
const MODEL_HINT='qwen3.8-4b';
const PERSONA=`你是雪，英文名 yuki，是住在用户桌面上的白发蓝裙女孩。用自然、温柔、灵动的中文交流，有自己的小想法，不过分撒娇，不使用客服套话。日常回复通常两到四句话；用户需要详细帮助时可以展开。记住当前对话中的信息。不编造已经执行的动作、联网、看屏幕、读取文件或控制电脑的结果：目前你只能文字交流，没有这些工具。不要输出思考过程、分析草稿或 <think> 标签，直接对用户说话。`;

function validateMessages(messages){
  if(!Array.isArray(messages)||!messages.length||messages.length>16)throw new Error('对话最多保留最近 16 条消息');
  let total=0;
  for(const item of messages){
    if(!item||!['user','assistant'].includes(item.role)||typeof item.content!=='string'||!item.content.trim()||item.content.length>6000)throw new Error('消息格式或长度不正确');
    total+=item.content.length;
  }
  if(total>14000||messages.at(-1).role!=='user')throw new Error('对话过长，请开启新对话');
  return messages.map(({role,content})=>({role,content}));
}
// Some reasoning GGUF templates prefill <think>; retain only the final answer.
function visibleAnswer(raw){
  const close=raw.lastIndexOf('</think>');
  if(close>=0)return raw.slice(close+8).replace(/<\|im_end\|>/g,'').trimStart();
  const open=raw.indexOf('<think>');
  if(open>=0)return raw.slice(0,open).trimStart();
  return raw.replace(/<\|im_end\|>/g,'').trimStart();
}
class Assistant {
  constructor({fetchImpl=fetch,endpoint=ENDPOINT}={}){this.fetch=fetchImpl;this.endpoint=endpoint;this.active=null;this.apiKey='';this.configured=false;}
  configure(config){this.cancel();this.endpoint=config.value.endpoint;this.preferredModel=config.value.model;this.apiKey=config.key;this.configured=true;}
  headers(){return this.apiKey?{Authorization:'Bearer '+this.apiKey}:{};}
  async models(){
    let response;
    const localDefault=!this.apiKey&&[ENDPOINT,'http://127.0.0.1:1234/v1'].includes(this.endpoint);
    for(const endpoint of [...new Set(localDefault?[this.endpoint,ENDPOINT,'http://127.0.0.1:1234/v1']:[this.endpoint])]){
      try{response=await this.fetch(endpoint+'/models',{headers:this.headers(),signal:AbortSignal.timeout(8000),redirect:'error'});this.endpoint=endpoint;break;}catch{}
    }
    if(!response)throw new Error('未连接模型服务，请检查 AI 助手中的模型服务设置，并确认服务已经启动。');
    if(!response.ok)throw new Error(`模型服务返回 ${response.status}，请检查地址与 API 密钥`);
    const data=await response.json();
    return {endpoint:this.endpoint,preferredModel:this.preferredModel||'',models:[...new Set([this.preferredModel,...(data.data||[]).map(item=>item.id)].filter(id=>typeof id==='string'&&id.length>0&&id.length<=300&&!/embed/i.test(id)))]};
  }
  cancel(){this.active?.abort();}
  async chat({id,model,messages},emit){
    if(typeof id!=='string'||!/^[a-zA-Z0-9-]{1,80}$/.test(id)||typeof model!=='string'||!model||model.length>300)throw new Error('模型或请求标识不正确');
    const history=validateMessages(messages);
    if(this.active)throw new Error('请等待当前回复完成');
    const controller=new AbortController();this.active=controller;
    const timer=setTimeout(()=>controller.abort(),180000);
    let raw='',reasoning=false,answer='';
    try{
      const response=await this.fetch(this.endpoint+'/chat/completions',{
        method:'POST',redirect:'error',signal:controller.signal,headers:{'Content-Type':'application/json',...this.headers()},
        body:JSON.stringify({model,messages:[{role:'system',content:PERSONA+'\n'+routineContext()},...history],temperature:0.6,top_p:0.95,max_tokens:1536,stream:true,
          // GGUF template options are local-runtime extensions. Cloud OpenAI
          // compatible servers may reject unknown request fields.
          ...(['localhost','127.0.0.1','[::1]'].includes(new URL(this.endpoint).hostname)?{top_k:20,chat_template_kwargs:{enable_thinking:false}}:{})})
      });
      if(!response.ok)throw new Error(`模型服务返回 ${response.status}，请检查模型名称、密钥、额度或本地模型是否已加载`);
      if(!response.body)throw new Error('模型没有返回响应');
      const reader=response.body.getReader(),decoder=new TextDecoder();let pending='',done=false;
      const line=value=>{
        if(!value.startsWith('data:'))return;
        const payload=value.slice(5).trim();if(!payload||payload==='[DONE]')return;
        const event=JSON.parse(payload);if(event.error)throw new Error('本地模型返回推理错误');
        const choice=event.choices?.[0],delta=choice?.delta||{};
        if(delta.reasoning_content||delta.reasoning){reasoning=true;emit({id,phase:'thinking',text:answer});}
        if(typeof delta.content==='string'){
          // In separate reasoning mode delta.content is the final response.
          raw+=delta.content;answer=visibleAnswer(raw);
          emit({id,phase:answer?'answer':'thinking',text:answer});
        }
        if(choice?.finish_reason==='length'&&!answer)throw new Error('模型在思考时达到回复上限，请重试或使用更适合即时聊天的模型');
      };
      while(!done){const chunk=await reader.read();done=chunk.done;pending+=decoder.decode(chunk.value,{stream:!done});
        const lines=pending.split('\n');pending=lines.pop()||'';for(const value of lines)line(value.trimEnd());
        if(pending.length>200000)throw new Error('模型响应格式异常');
      }
      if(pending.trim())line(pending.trimEnd());
      if(!answer.trim())throw new Error(reasoning?'模型只返回了思考内容，请重试':'模型未返回可显示的回答，请重试');
      return {text:answer.trim()};
    }catch(error){if(controller.signal.aborted)throw new Error('回复已停止或等待超时');throw error;}
    finally{clearTimeout(timer);controller.abort();if(this.active===controller)this.active=null;}
  }
}
module.exports={Assistant,validateMessages,visibleAnswer,PERSONA,MODEL_HINT,routineContext};
