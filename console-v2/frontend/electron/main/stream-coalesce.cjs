// Streaming frames carry the whole accumulated answer, so intermediate ones can be merged.
// Phase changes and the final frame always go through; the resolved chat() result stays the
// source of truth, and the renderer gets the text through flush() even if the stream stops early.
function coalesceUpdates(deliver,intervalMs=140,now=Date.now){
  let pending=null,timer=null,last=-Infinity;
  const flush=()=>{
    if(timer){clearTimeout(timer);timer=null;}
    if(pending){const value=pending;pending=null;last=now();deliver(value);}
  };
  return {push(value){
    if(value?.phase!=='answer'||now()-last>=intervalMs){
      if(timer){clearTimeout(timer);timer=null;}
      pending=null;last=now();deliver(value);return;
    }
    pending=value;
    timer=timer??setTimeout(flush,Math.max(0,intervalMs-(now()-last)));
  },flush};
}
module.exports={coalesceUpdates};
