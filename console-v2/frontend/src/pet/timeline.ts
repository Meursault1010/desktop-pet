export function frameAt(elapsed:number,durations:number[],loop=false,loopStart=0) {
  if(!durations.length||durations.some(v=>!Number.isFinite(v)||v<=0))throw new Error('帧时长无效');
  if(!Number.isInteger(loopStart)||loopStart<0||loopStart>=durations.length)throw new Error('循环起点无效');
  const total=durations.reduce((a,b)=>a+b,0),intro=durations.slice(0,loopStart).reduce((a,b)=>a+b,0);
  let time=Math.max(0,elapsed);
  if(loop&&time>=total)time=intro+(time-intro)%(total-intro);
  if(time>=total)return {index:durations.length-1,done:true};
  let index=0;while(index<durations.length-1&&time>=durations[index])time-=durations[index++];
  return {index,done:false};
}
