'use strict';
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
  constructor({fetchImpl=fetch,endpoint=ENDPOINT}={}){this.fetch=fetchImpl;this.endpoint=endpoint;this.active=null;}
  async models(){
    let response;
    for(const endpoint of [...new Set([this.endpoint,ENDPOINT,'http://127.0.0.1:1234/v1'])]){
      try{response=await this.fetch(endpoint+'/models',{signal:AbortSignal.timeout(3000),redirect:'error'});this.endpoint=endpoint;break;}catch{}
    }
    if(!response)throw new Error('未连接 LM Studio。请在设置 → 本地模型 API 启动服务（Bionic 端口 1235，经典版 1234），再点击重新连接。');
    if(!response.ok)throw new Error(`LM Studio 返回 ${response.status}，请检查本地服务与认证设置`);
    const data=await response.json();
    return {endpoint:this.endpoint,models:(data.data||[]).map(item=>item.id).filter(id=>typeof id==='string'&&id.length<=300&&!/embed/i.test(id))};
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
        method:'POST',redirect:'error',signal:controller.signal,headers:{'Content-Type':'application/json'},
        body:JSON.stringify({model,messages:[{role:'system',content:PERSONA},...history],temperature:0.6,top_p:0.95,top_k:20,max_tokens:1536,stream:true,chat_template_kwargs:{enable_thinking:false}})
      });
      if(!response.ok)throw new Error(`本地推理失败（${response.status}），请检查模型是否已加载、上下文是否足够`);
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
module.exports={Assistant,validateMessages,visibleAnswer,PERSONA,MODEL_HINT};
