"""Bake the approved master into a translation-only walk.

Each leg is a rigid sprite. Nothing rotates, scales or grounds per frame, so
the drawn sock and shoe silhouettes survive every sample unchanged. A planted
foot slides backwards at exactly the canvas stride; the other lifts, swings
forward and lands. Both shoes swing around the skirt's midline instead of the
wide standing stance, so one foot passes behind the other and the silhouettes
overlap and cross every step. Each sole keeps its authored depth on screen:
the far shoe stays higher than the near one instead of being pulled down to
the same floor. The skirt is sunk four pixels over the thighs, which shortens
the visible legs and hides both hip gaps without rewriting a sock pixel.
"""
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT/'assets/motion-v2'
SAMPLES = 120
AMPLITUDE = 16.  # source pixels; full cycle travels 4*A at 160/256 scale
LIFT = 5.        # source pixels of swing-foot clearance
BASELINE = 249.
UPSCALE = 4
BODY_WIPE = 211  # skirt hem ends above this row; only socks/shoes live below
BODY_DROP = 4.   # sinks the skirt over the thighs, shortening the visible leg
STANCE_GAP = 8.  # source px between the two sole centres during a walk step
WALK_CENTER = 128.  # body pivot the two soles straddle while walking


def sole(image):
    alpha=np.asarray(image.getchannel('A'))
    ys,xs=np.where(alpha>160)
    bottom=int(ys.max())
    return float(np.median(xs[ys>=bottom-UPSCALE/2]))/UPSCALE,bottom/UPSCALE


def translate(image,x,y):
    return image.transform(image.size,Image.Transform.AFFINE,
                           (1,0,-x*UPSCALE,0,1,-y*UPSCALE),Image.Resampling.BICUBIC)


def build():
    base=Image.open(ASSETS/'approved-walk-master.png').convert('RGBA')
    base=base.resize((256*UPSCALE,256*UPSCALE),Image.Resampling.LANCZOS)
    body=base.copy()
    body.paste((0,0,0,0),(0,BODY_WIPE*UPSCALE,256*UPSCALE,256*UPSCALE))
    legs=[]
    for box,pivot in [((0,205,129,256),(120,207)),((129,205,256,256),(136,207))]:
        box=tuple(v*UPSCALE for v in box)
        layer=Image.new('RGBA',base.size)
        layer.paste(base.crop(box),box[:2])
        # Keep only the sock and shoe. The hem above the wipe line is owned by
        # the body layer, so a moving leg can never drag skirt pixels with it.
        layer.paste((0,0,0,0),(0,0,256*UPSCALE,BODY_WIPE*UPSCALE))
        anchor_x,anchor_y=sole(layer)
        legs.append((layer,pivot,anchor_x,anchor_y))
    rig_folder=ASSETS/'walk-rig'
    rig_folder.mkdir(exist_ok=True)
    body.resize((256,256),Image.Resampling.LANCZOS).save(rig_folder/'body.png')
    # Both shoes swing around the body's centre line, not the average of the
    # authored stance anchors. That keeps the foot pair under the torso while
    # the swing foot still passes the planted one instead of sliding beside it.
    homes=[(WALK_CENTER-STANCE_GAP/2,legs[0][3]),(WALK_CENTER+STANCE_GAP/2,legs[1][3])]
    rig=[]
    for i,(layer,pivot,anchor_x,anchor_y) in enumerate(legs):
        layer.resize((256,256),Image.Resampling.LANCZOS).save(rig_folder/f'leg-{i}.png')
        alpha=np.asarray(layer.getchannel('A'))
        boundary=[]
        for x in range(0,alpha.shape[1],UPSCALE):
            ys=np.flatnonzero(alpha[:,x]>160)
            if len(ys):boundary.append([x/UPSCALE,float(ys[-1])/UPSCALE])
        for y in range(BODY_WIPE*UPSCALE,256*UPSCALE,UPSCALE):
            xs=np.flatnonzero(alpha[y]>160)
            if len(xs):boundary.extend([[float(xs[0])/UPSCALE,y/UPSCALE],[float(xs[-1])/UPSCALE,y/UPSCALE]])
        rig.append(dict(anchor=[anchor_x,anchor_y],home=[homes[i][0],homes[i][1]],
                        pivot=list(pivot),boundary=boundary))
    (rig_folder/'rig.json').write_text(json.dumps(rig),encoding='utf-8')
    images=[];contacts=[]
    for i in range(SAMPLES):
        phase=i/SAMPLES
        support=1 if phase<.5 else 0
        t=(phase*2)%1
        image=Image.new('RGBA',base.size)
        for leg,(source,_,anchor_x,anchor_y) in enumerate(legs):
            if leg==support:
                shift=AMPLITUDE*(1-2*t)
                lift=0.
            else:
                # Match the stance velocity at both takeoff and touchdown.
                shift=AMPLITUDE*(-1-2*t+12*t*t-8*t*t*t)
                lift=LIFT*math.sin(math.pi*t)**2
            home_x,home_y=homes[leg]
            image.alpha_composite(translate(source,home_x-anchor_x+shift,-lift))
            if leg==support:contact=(home_x+shift,home_y)
        image.alpha_composite(translate(body,0,BODY_DROP))
        images.append(image.resize((256,256),Image.Resampling.LANCZOS))
        contacts.append([contact[0],contact[1]])
    meta_path=ASSETS/'clips.json'
    meta=json.loads(meta_path.read_text(encoding='utf-8'))
    for name,keys,points in [
        ('walk-right',images,contacts),
        ('walk-left',[im.transpose(Image.Transpose.FLIP_LEFT_RIGHT) for im in images],
         [[255-x,y] for x,y in contacts]),
    ]:
        folder=ASSETS/name
        folder.mkdir(exist_ok=True)
        for i,image in enumerate(keys):image.save(folder/f'{i:02}.png')
        boxes=[im.getbbox() for im in keys]
        meta[name].update(frames=SAMPLES,stride=4*AMPLITUDE*160/256,
                          baseline=BASELINE/256,contacts=points,
                          bounds=[min(b[0] for b in boxes)/256,min(b[1] for b in boxes)/256,
                                  max(b[2] for b in boxes)/256,max(b[3] for b in boxes)/256],
                          method='rigid-translation-walk-v4',optical_flow=False)
    meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    return images


if __name__=='__main__':
    build()
    print('Baked 120 translation-only samples per direction, 40px logical stride.')
