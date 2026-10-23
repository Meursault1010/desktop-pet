export function normalizeOrder(saved:unknown,ids:readonly string[]):string[]{
 const known=new Set(ids),seen=new Set<string>();
 const result:string[]=[];
 for(const id of Array.isArray(saved)?saved:[])if(typeof id==='string'&&known.has(id)&&!seen.has(id)){result.push(id);seen.add(id);}
 return [...result,...ids.filter(id=>!seen.has(id))];
}
export function moveItem(order:readonly string[],from:string,to:string):string[]{
 const result=[...order],a=result.indexOf(from),b=result.indexOf(to);
 if(a<0||b<0||a===b)return result;
 result.splice(a,1);result.splice(b,0,from);return result;
}
