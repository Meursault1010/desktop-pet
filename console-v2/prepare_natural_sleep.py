"""Key the generated green background; normalize four prop-free RGBA poses."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT=Path(__file__).parent
if __name__=='__main__':
    raw=Image.open(ROOT/'action-work/icon-sleep-v2/raw-chroma.png').convert('RGBA')
    out=ROOT/'assets/icon-sleep-v2';out.mkdir(parents=True,exist_ok=True)
    preview=Image.new('RGBA',(1024,256),(45,55,72,255))
    for index,name in enumerate(('left','right','back','front')):
        col,row=index%2,index//2
        cell=raw.crop((col*raw.width//2,row*raw.height//2,(col+1)*raw.width//2,(row+1)*raw.height//2))
        data=np.asarray(cell).astype('float32')
        rgb=data[:,:,:3]; green=rgb[:,:,1]; others=np.maximum(rgb[:,:,0],rgb[:,:,2])
        if np.mean((green>180)&(green-others>80))<.2:
            raise ValueError('Expected a clean green background, inspect generated artwork')
        # Gateway green is compressed/uneven (~15,238,26), not pure #00ff00.
        # Character art is white/blue, so excess green safely identifies matte.
        alpha=np.clip(1-np.maximum(green-others-8,0)/130,0,1)
        alpha[alpha<.04]=0
        # Reverse chroma mixing on soft silhouette edges, never whiten hair.
        background=np.array([15,238,26],dtype="float32")
        rgb[:]=(rgb-background*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],.001)
        data[:,:,:3]=np.clip(rgb,0,255);data[:,:,3]=alpha*255
        count,labels,stats,_=cv2.connectedComponentsWithStats((alpha>.08).astype('uint8'))
        largest=1+np.argmax(stats[1:,cv2.CC_STAT_AREA])
        component=(labels==largest).astype('uint8')
        component=cv2.dilate(component,np.ones((3,3),dtype='uint8'))
        data[:,:,3][component==0]=0
        image=Image.fromarray(data.astype('uint8'))
        image=image.crop(image.getbbox());image.thumbnail((220,220),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(256,256));canvas.alpha_composite(image,((256-image.width)//2,240-image.height))
        canvas.save(out/f'{name}.png');preview.alpha_composite(canvas,(index*256,0))
    qa=ROOT/'qa/icon-sleep-v2';qa.mkdir(parents=True,exist_ok=True)
    preview.save(qa/'poses.png');print(out)
