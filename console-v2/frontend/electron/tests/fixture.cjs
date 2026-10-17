const version=process.argv.includes('bad-version')?999:1;
process.stdout.write(JSON.stringify({type:'ready',protocol:version})+'\n');
let buffer='';
process.stdin.setEncoding('utf8');
process.stdin.on('data',chunk=>{buffer+=chunk;let index;
  while((index=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,index);buffer=buffer.slice(index+1);const {id,name,payload}=JSON.parse(line);
    if(payload.key==='opacity')continue;
    if(name==='shutdown'){process.stdout.write(JSON.stringify({type:'response',id,ok:true})+'\n');process.exit(0);}
    if(name==='jump'){process.stdout.write('not json\n');continue;}
    process.stdout.write(JSON.stringify({type:'response',id,ok:true,state:{revision:1,preferences:{...payload}}})+'\n');
  }
});
process.stdin.on('end',()=>process.exit(0));
