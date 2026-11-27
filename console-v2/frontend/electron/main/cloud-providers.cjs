'use strict';
const cloudPresets=require('../shared/cloud-presets.json');
const presetHosts=new Set(cloudPresets.map(preset=>new URL(preset.endpoint).hostname));

function modelListHeaders(endpoint,apiKey){
  const headers=apiKey?{Authorization:`Bearer ${apiKey}`}:{};
  // Claude's OpenAI-compatible chat accepts a Bearer token. Its Models API also requires a version.
  if(new URL(endpoint).hostname==='api.anthropic.com')headers['anthropic-version']='2026-10-21';
  return headers;
}

function completionOptions(endpoint,model,limit){
  const hostname=new URL(endpoint).hostname;
  if(!presetHosts.has(hostname))return {temperature:0.6,top_p:0.95,max_tokens:limit};
  if(hostname==='api.openai.com'){
    const reasoning=/^(gpt-5|o[134](?:-|$))/.test(model);
    return {max_completion_tokens:reasoning?Math.max(4096,limit):limit};
  }
  if(hostname==='api.groq.com')return {max_completion_tokens:Math.max(4096,limit)};
  if(hostname==='api.deepseek.com'&&model==='deepseek-flash'){
    return {max_tokens:limit,thinking:{type:'disabled'}};
  }
  // Each provider supplies its own compatible sampling defaults.
  return {max_tokens:Math.max(4096,limit)};
}

module.exports={modelListHeaders,completionOptions};
