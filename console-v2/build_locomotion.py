"""Extract reviewed gait keys and articulate grip poses without alpha fading."""
from pathlib import Path
import json,math
import cv2
import numpy as np
from PIL import Image,ImageDraw
from prepare_icon_interactions import chroma_cutout
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'assets/motion-v2'

def master(kind):
    image=Image.open(ROOT/f'action-work/locomotion/{kind}/raw.png').convert('RGBA')
    if abs(image.width/image.height-1.5)>.025:raise ValueError('Unexpected sheet aspect ratio')
    # Gateway may return 1264x848 despite requested size; normalize whole sheet,
    # never fit the six characters separately and destroy common character scale.
    image=image.resize((1536,1024),Image.Resampling.LANCZOS)
    cells=[]
    for i in range(6):
        cell=image.crop((i%3*512,i//3*512,i%3*512+512,i//3*512+512))
        rgb=np.asarray(cell)[:,:,:3].astype('float32')
        core=(rgb[:,:,1]-np.maximum(rgb[:,:,0],rgb[:,:,2])<90).astype('uint8')
        count,labels,stats,_=cv2.connectedComponentsWithStats(core)
        keep=np.zeros(core.shape,dtype='uint8')
        for label in range(1,count):
            if stats[label,cv2.CC_STAT_AREA]>=50:keep[labels==label]=1
        keep=cv2.dilate(keep,np.ones((5,5),dtype='uint8'))
        data=np.array(chroma_cutout(cell,margin=0));data[keep==0]=0
        # Remove weak green JPEG/resize halos, preserving edge antialiasing.
        data[data[:,:,3]<12]=0
        cut=Image.fromarray(data)
        box=cut.getchannel('A').getbbox()
        if not box or min(box[:2])<4 or max(box[2:])>508:raise ValueError('Cropped character')
        cells.append(cut)
    return cells

def warp(image,dx,dy):
    data=np.array(image).astype('float32')/255;data[:,:,:3]*=data[:,:,3:4]
    yy,xx=np.mgrid[:512,:512].astype('float32')
    out=cv2.remap(data,(xx-dx).astype('float32'),(yy-dy).astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    out[:,:,:3]/=np.maximum(out[:,:,3:4],1e-6)
    return Image.fromarray(np.clip(out*255,0,255).astype('uint8'))

def bounds(frames):
    boxes=[im.getbbox() for im in frames]
    return [min(b[0] for b in boxes)/256,min(b[1] for b in boxes)/256,max(b[2] for b in boxes)/256,max(b[3] for b in boxes)/256]

def save_clip(name,frames,**extra):
    folder=OUT/name;folder.mkdir(parents=True,exist_ok=True)
    frames=[im.resize((256,256),Image.Resampling.LANCZOS) for im in frames]
    for index,image in enumerate(frames):image.save(folder/f'{index:02}.png')
    return dict(frames=len(frames),bounds=bounds(frames),**extra)

def main():
    OUT.mkdir(parents=True,exist_ok=True);meta={};clips={}
    for direction in ('left','right'):
        frames=master('walk-'+direction)
        # Ground each original key at the same baseline, retaining stride shape.
        grounded=[]
        for image in frames:
            bottom=image.getbbox()[3];canvas=Image.new('RGBA',(512,512));canvas.alpha_composite(image,(0,474-bottom));grounded.append(canvas)
        name='walk-'+direction;clips[name]=grounded
        meta[name]=save_clip(name,grounded,stride=72,baseline=474/512)
    grips=master('grips')
    # Measured hand rail coordinates on the normalized sheet. Align phases at
    # the same upper hand; phase differences never move the rail horizontally.
    specs={
      'climb-left':dict(indices=[0,1],hands=[(352,83),(350,83)],contact=[352/512,83/512],rail=352,support_bottom=.92),
      'climb-right':dict(indices=[2,3],hands=[(164,84),(166,82)],contact=[164/512,84/512],rail=164,support_bottom=.92),
      'hang':dict(indices=[4,5],hands=[(247,34),(225,33)],contact=[247/512,34/512],rail=247,support_bottom=.92),
    }
    yy,xx=np.mgrid[:512,:512].astype('float32')
    for name,spec in specs.items():
        bases=[];cx,cy=spec['hands'][0]
        for index,(hx,hy) in zip(spec['indices'],spec['hands']):
            canvas=Image.new('RGBA',(512,512));canvas.alpha_composite(grips[index],(cx-hx,cy-hy));bases.append(canvas)
        frames=[]
        for frame in range(24):
            phase=frame*math.tau/24
            if name=='hang':
                # Both grip points remain fixed; displacement grows BELOW arms.
                depth=np.clip((yy-100)/360,0,1)
                dx=np.sin(phase)*15*depth**1.6
                dy=(1-math.cos(phase*2))*2.2*depth
                image=warp(bases[0],dx,dy)
            else:
                # Reach/regrip: hands and feet stay on the rail (x invariant),
                # opposite limbs bend and step vertically; torso stays stable.
                rail=spec['rail'];near=np.exp(-((xx-rail)/68)**2)
                upper=np.exp(-((yy-84)/48)**2);lower=np.exp(-((yy-180)/48)**2)
                foot1=np.exp(-((yy-377)/42)**2);foot2=np.exp(-((yy-460)/38)**2)
                dy=near*(np.sin(phase)*15*upper-np.sin(phase)*15*lower+np.sin(phase+1)*19*foot1-np.sin(phase+1)*19*foot2)
                # A bent knee changes too; fingers/soles remain on same x rail.
                dx=np.sin(phase)*4*np.exp(-((yy-310)/70)**2)*np.exp(-((xx-(rail-55 if name=='climb-left' else rail+55))/65)**2)
                image=warp(bases[0],dx,dy)
            frames.append(image)
        clips[name]=frames
        meta[name]=save_clip(name,frames,contact=spec['contact'],support_bottom=spec['support_bottom'],stride=44,cycle=2.4 if name=='hang' else 1.8)
    (OUT/'clips.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    qa=ROOT/'qa/locomotion';qa.mkdir(parents=True,exist_ok=True)
    review=Image.new('RGB',(1536,1024),'#202b40')
    for i,image in enumerate(grips):review.paste(image,(i%3*512,i//3*512),image)
    review.save(qa/'grips-cutout.png')
    animation=[]
    for tick in range(72):
        canvas=Image.new('RGBA',(1100,300),'#202b40');draw=ImageDraw.Draw(canvas)
        for col,(name,images) in enumerate(clips.items()):
            draw.text((col*220+8,12),name,fill='#eff5ff')
            if name.startswith('climb'):
                rx=specs[name]['rail']/512*180+col*220+20;draw.line((rx,35,rx,280),fill='#85b6ef',width=3)
            if name=='hang':draw.line((col*220+10,42,col*220+210,42),fill='#85b6ef',width=3)
            index=int(tick/2)%6 if name.startswith('walk') else tick%24
            image=images[index].resize((180,180),Image.Resampling.LANCZOS)
            y=42-round(180*meta[name]['contact'][1]) if name=='hang' else 60
            canvas.alpha_composite(image,(col*220+20,y))
        animation.append(canvas.convert('RGB'))
    animation[0].save(qa/'motion-review.gif',save_all=True,append_images=animation[1:],duration=75,loop=0,disposal=2)
    animation[0].save(qa/'motion-review.png')
    print('Published two authored walk cycles and three articulated grip clips.')

if __name__=='__main__':main()
