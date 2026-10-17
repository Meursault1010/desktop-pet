"""Normalize generated prop-free poses into stable transparent canvases."""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
if __name__ == '__main__':
    raw=Image.open(ROOT/'action-work/icon-sleep/raw.png').convert('RGBA')
    out=ROOT/'assets/icon-sleep'; out.mkdir(parents=True,exist_ok=True)
    for index,name in enumerate(('left','back','right')):
        cell=raw.crop((round(index*raw.width/3),0,round((index+1)*raw.width/3),raw.height))
        data=np.array(cell)
        _,labels,stats,_=cv2.connectedComponentsWithStats((data[:,:,3]>80).astype('uint8'))
        largest=1+np.argmax(stats[1:,cv2.CC_STAT_AREA])
        data[:,:,3][labels!=largest]=0
        image=Image.fromarray(data); image=image.crop(image.getbbox())
        image.thumbnail((220,220),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(256,256)); canvas.alpha_composite(image,((256-image.width)//2,240-image.height))
        canvas.save(out/f'{name}.png')
    print(out)
