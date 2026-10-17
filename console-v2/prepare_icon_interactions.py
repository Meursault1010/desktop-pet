"""Extract six drafts and a dark/light review sheet, never publish unseen art.

Run after generation, inspect draft PNGs, then author measured contacts and
part masks. This deliberately does not copy drafts into production assets.
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
NAMES=('sit-front','sit-back','perch-front','prone-front','prone-back','perch-back')


def chroma_cutout(cell,margin=8):
    data=np.array(cell.convert('RGBA'),dtype=np.float32)
    rgb=data[:,:,:3]
    excess=rgb[:,:,1]-np.maximum(rgb[:,:,0],rgb[:,:,2])
    background=excess>100
    if background.mean()<.2:
        raise ValueError('Expected green background; review artwork before extracting')
    # Estimate actual generated chroma rather than assuming pure RGB green.
    key=np.median(rgb[background],axis=0)
    strength=float(key[1]-max(key[0],key[2]))
    alpha=np.clip(1-np.maximum(excess-7,0)/max(1,strength-7),0,1)
    alpha[alpha<.025]=0
    count,labels,stats,_=cv2.connectedComponentsWithStats((alpha>.1).astype('uint8'))
    if count<2: raise ValueError('No character found')
    # Keep small detached accessories nearby; discard isolated green-matte noise.
    keep=np.zeros(alpha.shape,dtype='uint8')
    for label in range(1,count):
        if stats[label,cv2.CC_STAT_AREA]>=12: keep[labels==label]=1
    keep=cv2.dilate(keep,np.ones((3,3),dtype='uint8'))
    alpha[keep==0]=0
    rgb=(rgb-key*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.001)
    data[:,:,:3]=np.clip(rgb,0,255);data[:,:,3]=alpha*255
    # Hidden RGB from inverse keying must also be zero. Some image consumers
    # inspect all channels for bounds or composite in straight-alpha space.
    data[alpha==0]=0
    image=Image.fromarray(data.astype('uint8'))
    if not image.getbbox(): raise ValueError('Empty sprite')
    l,t,r,b=image.getbbox()
    if l<margin or t<margin or r>cell.width-margin or b>cell.height-margin:
        raise ValueError('Character touches cell boundary; inspect for cropped anatomy')
    # Keep the original canvas and common scale: do not independently fit each
    # bounding box, which would make horizontal poses much smaller than sitters.
    return image


if __name__=='__main__':
    folder=ROOT/'action-work/icon-interactions'
    raw=Image.open(folder/'raw.png')
    if raw.size!=(1536,1024): raise ValueError(f'Unexpected sheet layout: {raw.size}')
    out=folder/'drafts';out.mkdir(parents=True,exist_ok=True)
    qa=Image.new('RGB',(1536,2176),'#fafbfe')
    draw=ImageDraw.Draw(qa)
    for index,name in enumerate(NAMES):
        col,row=index%3,index//3
        cell=raw.crop((col*512,row*512,(col+1)*512,(row+1)*512))
        sprite=chroma_cutout(cell);sprite.save(out/f'{name}.png')
        for section,color in enumerate(('#f4f6fa','#202b40')):
            panel=Image.new('RGBA',(512,544),color)
            panel.alpha_composite(sprite,(0,24))
            qa.paste(panel.convert('RGB'),(col*512,section*1088+row*544))
            draw.text((col*512+12,section*1088+row*544+8),name,
                      fill='#243147' if section==0 else '#eff5ff')
    qa.save(folder/'review.png')
    print(f'Draft sprites: {out}')
    print(f'Visual review: {folder / "review.png"}')
