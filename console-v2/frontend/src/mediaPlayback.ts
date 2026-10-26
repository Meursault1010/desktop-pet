import type {DesktopSnapshot} from './host/types';
export function mediaPosition(media:DesktopSnapshot['media'],now:number){
 const elapsed=media.status==='Playing'&&media.observedAt?Math.max(0,Math.min(10,(now-media.observedAt)/1000))*(media.rate??1):0;
 return Math.max(media.start||0,Math.min(media.duration||0,(media.position||0)+elapsed));
}
export function lyricIndex(lines:{at:number}[],position:number){
 let low=0,high=lines.length-1,result=-1;
 while(low<=high){const mid=(low+high)>>>1;if(lines[mid].at<=position){result=mid;low=mid+1;}else high=mid-1;}
 return result;
}
