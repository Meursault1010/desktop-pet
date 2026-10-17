import type {Clip,PetRenderer} from './renderer';
import {frameAt} from './timeline.ts';

export class PngRenderer implements PetRenderer {
  private context:CanvasRenderingContext2D;
  private idle:HTMLImageElement|null=null;
  private eyes:Record<string,HTMLImageElement>={};
  private blinkAt=performance.now()+3500;
  private image:HTMLImageElement|null=null;
  private clip:Clip|null=null;
  private started=performance.now();
  private loop=false;private speed=1;private request=0;private disposed=false;private generation=0;
  private alpha=1;private scale=1;
  private canvas:HTMLCanvasElement;
  constructor(canvas:HTMLCanvasElement) {
    this.canvas=canvas;
    const context=canvas.getContext('2d',{willReadFrequently:true});if(!context)throw new Error('Canvas unavailable');
    this.context=context;this.tick=this.tick.bind(this);this.request=requestAnimationFrame(this.tick);
  }
  private load(url:string):Promise<HTMLImageElement>{
    if(!url.startsWith('/pet-assets/'))return Promise.reject(new Error('只允许已打包角色素材'));
    return new Promise((resolve,reject)=>{const image=new Image();image.onload=()=>resolve(image);image.onerror=()=>reject(new Error(`图片加载失败：${url}`));image.src=url;});
  }
  async loadCharacter(id:string){
    if(id!=='yuki')throw new Error('未知角色');
    const [open,half,closed]=await Promise.all(['open','half','closed'].map(name=>this.load(`/pet-assets/living-idle/${name}.png`)));
    if([open,half,closed].some(image=>image.width!==2048||image.height!==2048))throw new Error('待机图集尺寸无效');
    this.idle=open;this.eyes={open,half,closed};this.started=performance.now();
  }
  async playAction(clip:Clip,loop=false,speed=1){
    if(!Number.isFinite(speed)||speed<.25||speed>2||clip.frames!==clip.durations.length||clip.cell!==256||!Number.isInteger(clip.columns)||clip.columns<1)throw new Error('动作定义无效');
    frameAt(0,clip.durations,loop,clip.loop_start??0);
    const token=++this.generation;const image=await this.load('/pet-assets/'+clip.atlas.replace(/^actions\//,'actions/'));
    if(image.width<Math.min(clip.frames,clip.columns)*clip.cell||image.height<Math.ceil(clip.frames/clip.columns)*clip.cell)throw new Error('动作图集缺帧');
    if(token!==this.generation||this.disposed)return;
    this.image=image;this.clip=clip;this.loop=loop;this.speed=speed;this.started=performance.now();
  }
  async stopAction(){this.generation++;this.clip=null;this.image=null;this.started=performance.now();}
  setParameter(name:'opacity'|'scale',value:number){if(!Number.isFinite(value))throw new Error('参数无效');if(name==='opacity')this.alpha=Math.max(0,Math.min(1,value));else this.scale=Math.max(.5,Math.min(2,value));}
  private tick(now:number){
    if(this.disposed)return;const context=this.context;context.clearRect(0,0,this.canvas.width,this.canvas.height);
    context.imageSmoothingEnabled=!this.clip?.pixel_art;context.globalAlpha=this.alpha;
    let image=this.idle,index=Math.floor(((now-this.started)%4800)/75),columns=8;
    if(this.clip&&this.image){const frame=frameAt((now-this.started)*this.speed,this.clip.durations,this.loop,this.clip.loop_start??0);
      if(frame.done&&!this.loop){void this.stopAction();}else{image=this.image;index=frame.index;columns=this.clip.columns;}}
    else if(this.idle){const blink=now-this.blinkAt;
      image=blink>=50&&blink<120?this.eyes.closed:blink>=0&&blink<170?this.eyes.half:this.eyes.open;
      if(blink>=170)this.blinkAt=now+2800+Math.random()*4000;
    }
    if(image){const size=256*this.scale;context.drawImage(image,(index%columns)*256,Math.floor(index/columns)*256,256,256,(this.canvas.width-size)/2,(this.canvas.height-size)/2,size,size);}
    this.request=requestAnimationFrame(this.tick);
  }
  dispose(){this.disposed=true;this.generation++;cancelAnimationFrame(this.request);this.context.clearRect(0,0,this.canvas.width,this.canvas.height);}
}
