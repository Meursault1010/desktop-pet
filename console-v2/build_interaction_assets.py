"""Publish reviewed cutouts with measured contacts and local animation layers.

Warp only hair ends and free feet; pelvis/forearms stay on their support.
Blink images replace the iris with a hand-authored closed eyelid, not a fade.
Runtime needs Qt only; Pillow/numpy/OpenCV are build-time dependencies.
"""
from pathlib import Path
import json
import math
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
# Measurements on the original 512px cells, retained at a common scale.
POSES={
 'sit-front':dict(name='坐在图标上 · 转头',contact=[250,360],support='top',eyes=[[258,180,40,31],[321,168,40,32]],feet=[185,449],hair=[414,321],dress=[140,277,349,407]),
 'sit-back':dict(name='坐在图标上 · 回眸',contact=[206,340],support='top',eyes=[[181,159,15,23],[226,174,28,25]],feet=[270,435],hair=[358,334],dress=[104,265,272,359]),
 'perch-front':dict(name='斜坐倚靠 · 朝向你',contact=[338,284],support='side',target_x=.9,eyes=[[250,182,30,24],[310,170,31,25]],feet=[100,433],hair=[401,318],dress=[130,282,342,424]),
 'prone-front':dict(name='趴在图标上 · 托腮',contact=[285,350],support='top',eyes=[[131,259,30,22],[196,251,31,24]],feet=[438,205],hair=[337,361],dress=[286,246,442,367]),
 'prone-back':dict(name='趴在图标上 · 回头',contact=[208,361],support='top',eyes=[[370,231,26,23],[416,221,17,23]],feet=[87,243],hair=[298,359],dress=[110,276,280,389]),
 'perch-back':dict(name='斜坐倚靠 · 侧背',contact=[142,247],support='side',target_x=.1,eyes=[[221,157,22,23],[262,146,15,22]],feet=[394,400],hair=[130,347],dress=[202,279,355,421]),
}

def blink_image(source, eyes):
    image=source.copy(); draw=ImageDraw.Draw(image)
    for cx,cy,w,h in eyes:
        # Eye coordinates are deliberately local, leaving brows/hair untouched.
        box=(cx-w*.59,cy-h*.57,cx+w*.59,cy+h*.60)
        draw.ellipse(box,fill=(255,238,236,255))
        points=[(cx-w*.52+i*w*1.04/16,cy+1+math.sin(i*math.pi/16)*h*.12) for i in range(17)]
        draw.line(points,fill=(55,58,100,255),width=3)
    return image

def warp(source, spec, phase):
    data=np.array(source,dtype=np.float32)/255
    data[:,:,:3]*=data[:,:,3:4]  # interpolate premultiplied, avoiding edge halos
    yy,xx=np.mgrid[:512,:512].astype('float32');dx=np.zeros_like(xx);dy=dx.copy()
    for key,radius,amplitude in [('feet',64,2.4),('hair',60,1.7)]:
        x,y=spec[key];fall=np.exp(-((xx-x)**2+(yy-y)**2)/(radius**2*.55))
        cx,cy=spec['contact']
        fall*=np.clip(((xx-cx)**2+(yy-cy)**2)/55**2,0,1)
        dx+=fall*math.sin(phase+(0 if key=='feet' else 1.3))*amplitude
        dy+=fall*math.sin(phase*.999+(1 if key=='feet' else .4))*amplitude*.5
    out=cv2.remap(data,xx-dx,yy-dy,cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    out[:,:,:3]/=np.maximum(out[:,:,3:4],1e-6)
    return Image.fromarray(np.clip(out*255,0,255).astype('uint8')).resize((256,256),Image.Resampling.LANCZOS)

def main():
    out=ROOT/'assets/icon-interactions';out.mkdir(parents=True,exist_ok=True)
    metadata={}
    for name,spec in POSES.items():
        base=Image.open(ROOT/f'action-work/icon-interactions/drafts/{name}.png').convert('RGBA')
        folder=out/name;folder.mkdir(exist_ok=True)
        base.resize((256,256),Image.Resampling.LANCZOS).save(folder/'base.png')
        closed=blink_image(base,spec['eyes'])
        # 16 continuous local-motion samples plus matching blink samples.
        for index in range(16):
            for kind,source in [('open',base),('blink',closed)]:
                warp(source,spec,index*math.tau/16).save(folder/f'{kind}-{index:02}.png')
        rgba=np.array(base);r,g,b,a=[rgba[:,:,i].astype(float) for i in range(4)]
        l,t,rr,bb=spec['dress']; yy,xx=np.mgrid[:512,:512]
        # Authored dress-only ROI AND conservative blue material mask. Hair,
        # skin, legs, accessories and pale hair shadows cannot enter this matte.
        allowed=(xx>=l)&(xx<rr)&(yy>=t)&(yy<bb)&(a>0)&(b>80)&(r<b*.70)&(b-r>40)
        matte=Image.fromarray((allowed*255).astype('uint8')).resize((256,256),Image.Resampling.NEAREST)
        small=np.array(base.resize((256,256),Image.Resampling.LANCZOS)).astype(float)
        sr,sg,sb,sa=[small[:,:,i] for i in range(4)]
        eligible=(sa>0)&(sb>80)&(sr<sb*.70)&(sb-sr>40)
        matte=Image.fromarray((np.array(matte)*eligible).astype('uint8'))
        matte.save(folder/'skirt.png')
        metadata[name]=dict(name=spec['name'],contact=[v/512 for v in spec['contact']],support=spec['support'],target_x=spec.get('target_x',.5),frames=16,cycle=6.4)
    (out/'poses.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8')
    # Review animation at actual desktop size, on both dark and light surfaces.
    frames=[]
    for step in range(64):
        canvas=Image.new('RGB',(960,470),'#f4f6fa');draw=ImageDraw.Draw(canvas)
        draw.rectangle((0,235,960,470),fill='#202b40')
        for index,(name,spec) in enumerate(POSES.items()):
            blink=step in (28,29,55)
            sprite=Image.open(out/name/f'{"blink" if blink else "open"}-{step%16:02}.png').convert('RGBA').resize((160,160),Image.Resampling.LANCZOS)
            for y in (40,275):canvas.paste(sprite,(index*160,y),sprite)
            draw.text((index*160+5,12),name,fill='#26334b')
        frames.append(canvas)
    frames[0].save(ROOT/'action-work/icon-interactions/animation-review.gif',save_all=True,append_images=frames[1:],duration=100,loop=0,disposal=2)
    frames[28].save(ROOT/'action-work/icon-interactions/blink-review.png')
    print('Published six reviewed poses, 192 local animation frames and dress mattes.')

if __name__=='__main__':main()
