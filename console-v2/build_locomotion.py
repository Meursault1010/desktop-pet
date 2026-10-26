"""Extract reviewed gait keys and articulate grip poses without alpha fading."""
from pathlib import Path
import argparse,json,math
import cv2
import numpy as np
from PIL import Image,ImageDraw
from prepare_icon_interactions import chroma_cutout
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'assets/motion-v2'
CLIMB_FRAMES=24

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

def authored_cycle(name,spec,grips):
    """Cycle the two authored climbing phases through one offline flow pass.

    The old sine field displaced neighbouring columns by different amounts,
    which sheared hair and dress trim. Flow between the two authored poses
    moves real limbs and leaves every source pixel on its own body.
    """
    from build_action_inbetweens import interpolate
    cx,cy=spec['hands'][0]
    ends=[]
    for index,(hx,hy) in zip(spec['indices'],spec['hands']):
        canvas=Image.new('RGBA',(512,512));canvas.alpha_composite(grips[index],(cx-hx,cy-hy))
        ends.append(canvas.resize((256,256),Image.Resampling.LANCZOS))
    samples,report=interpolate(np.asarray(ends[0]),np.asarray(ends[1]),(name,0),(name,1),{})
    if not report['accepted']:raise ValueError(f'{name} 攀爬相位插值不合格：{report}')
    forward=[Image.fromarray(sample) for sample in samples]
    cycle=forward+forward[-2:0:-1]
    return [cycle[i] for i in range(0,len(cycle),max(1,len(cycle)//CLIMB_FRAMES))][:CLIMB_FRAMES]


def hang_cycle(spec,grips):
    yy,xx=np.mgrid[:512,:512].astype('float32')
    cx,cy=spec['hands'][0]
    canvas=Image.new('RGBA',(512,512));canvas.alpha_composite(grips[spec['indices'][0]],(cx-spec['hands'][0][0],cy-spec['hands'][0][1]))
    frames=[]
    for frame in range(24):
        phase=frame*math.tau/24
        # Both grip points remain fixed; displacement grows BELOW arms.
        depth=np.clip((yy-100)/360,0,1)
        dx=np.sin(phase)*15*depth**1.6
        dy=(1-math.cos(phase*2))*2.2*depth
        frames.append(warp(canvas,dx,dy))
    return frames


def build_walks(meta,clips):
    for direction in ('left','right'):
        frames=master('walk-'+direction)
        # Ground each original key at the same baseline, retaining stride shape.
        grounded=[]
        for image in frames:
            bottom=image.getbbox()[3];canvas=Image.new('RGBA',(512,512));canvas.alpha_composite(image,(0,474-bottom));grounded.append(canvas)
        name='walk-'+direction;clips[name]=grounded
        meta[name]=save_clip(name,grounded,stride=72,baseline=474/512)


def build_grips(meta,clips):
    grips=master('grips')
    # Measured hand rail coordinates on the normalized sheet. Align phases at
    # the same upper hand; phase differences never move the rail horizontally.
    specs={
      'climb-left':dict(indices=[0,1],hands=[(352,83),(350,83)],contact=[352/512,83/512],rail=352,support_bottom=.92),
      'climb-right':dict(indices=[2,3],hands=[(164,84),(166,82)],contact=[164/512,84/512],rail=164,support_bottom=.92),
      'hang':dict(indices=[4,5],hands=[(247,34),(225,33)],contact=[247/512,34/512],rail=247,support_bottom=.92),
    }
    for name,spec in specs.items():
        if name=='hang':frames=hang_cycle(spec,grips)
        else:frames=authored_cycle(name,spec,grips)
        clips[name]=frames
        meta[name]=save_clip(name,frames,contact=spec['contact'],support_bottom=spec['support_bottom'],stride=44,cycle=2.4 if name=='hang' else 1.8)
    return grips


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--grips-only',action='store_true',
                        help='rebuild climbing clips only; walk clips stay as calibrated')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    meta={};clips={};grip_frames=None
    if args.grips_only:
        # Calibration rewrites clips.json from its own metadata backup, so a
        # grips-only pass must not publish walk entries or contacts.
        build_grips(meta,clips)
    else:
        build_walks(meta,clips)
        grip_frames=build_grips(meta,clips)
        (OUT/'clips.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    qa=ROOT/'qa/locomotion';qa.mkdir(parents=True,exist_ok=True)
    if grip_frames is not None:
        review=Image.new('RGB',(1536,1024),'#202b40')
        for i,image in enumerate(grip_frames):review.paste(image,(i%3*512,i//3*512),image)
        review.save(qa/'grips-cutout.png')
    animation=[]
    for tick in range(72):
        canvas=Image.new('RGBA',(1100,300),'#202b40');draw=ImageDraw.Draw(canvas)
        for col,(name,images) in enumerate(clips.items()):
            draw.text((col*220+8,12),name,fill='#eff5ff')
            if name.startswith('climb'):
                rx=meta[name]['contact'][0]*180+col*220+20;draw.line((rx,35,rx,280),fill='#85b6ef',width=3)
            if name=='hang':draw.line((col*220+10,42,col*220+210,42),fill='#85b6ef',width=3)
            index=tick%meta[name]['frames']
            image=images[index].resize((180,180),Image.Resampling.LANCZOS)
            y=42-round(180*meta[name]['contact'][1]) if name=='hang' else 60
            canvas.alpha_composite(image,(col*220+20,y))
        animation.append(canvas.convert('RGB'))
    if animation:
        animation[0].save(qa/'motion-review.gif',save_all=True,append_images=animation[1:],duration=75,loop=0,disposal=2)
        animation[0].save(qa/'motion-review.png')
    print('Published two authored walk cycles and three articulated grip clips.')

if __name__=='__main__':main()
