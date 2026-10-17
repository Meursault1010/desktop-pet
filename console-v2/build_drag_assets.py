"""Extract reviewed reach art; no runtime image-library dependency."""
from pathlib import Path
import json
import numpy as np
from PIL import Image,ImageDraw
from prepare_icon_interactions import chroma_cutout
root=Path(__file__).resolve().parent;out=root/'assets/drag-resist';out.mkdir(exist_ok=True)
raw=Image.open(root/'action-work/drag-resist/raw.png').convert('RGBA').resize((1536,1024))
# Palm centers measured from the reviewed cells, in their original 512 canvas.
specs=[('upper-left',(167,120)),('up',(257,68)),('upper-right',(0,0)),('left',(130,202)),('down',(219,312)),('right',(344,205))]
meta={}
for i,(name,hand) in enumerate(specs):
 if name=='upper-right':
  image=Image.open(root/'action-work/drag-resist/upper-right.png').convert('RGBA')
  # The correction returned real alpha, rather than a green matte.
  if image.getchannel('A').getextrema()[0]==255:image=chroma_cutout(image,margin=0)
  box=image.getchannel('A').getbbox();crop=image.crop(box)
  scale=430/crop.height;crop=crop.resize((round(crop.width*scale),430),Image.Resampling.LANCZOS)
  cell=Image.new('RGBA',(512,512));left=(512-crop.width)//2;cell.alpha_composite(crop,(left,40))
  # Original correction palm center approx (884,230) on 1280 canvas.
  hand=(left+(884-box[0])*scale,40+(230-box[1])*scale)
 else:cell=chroma_cutout(raw.crop((i%3*512,i//3*512,i%3*512+512,i//3*512+512)),margin=0)
 cell.resize((256,256),Image.Resampling.LANCZOS).save(out/f'{name}.png')
 meta[name]={'hand':[hand[0]/2,hand[1]/2]}
(out/'poses.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
review=Image.new('RGB',(960,640),'#202b40');d=ImageDraw.Draw(review)
for i,(name,_) in enumerate(specs):
 im=Image.open(out/f'{name}.png').resize((300,300));x=i%3*320;y=i//3*320
 review.paste(im,(x,y+20),im);d.text((x+8,y+4),name,fill='white')
 hx,hy=meta[name]['hand'];hx=x+hx*300/256;hy=y+20+hy*300/256
 d.ellipse((hx-4,hy-4,hx+4,hy+4),outline='#faac66',width=2)
qa=root/'qa/drag';qa.mkdir(exist_ok=True);review.save(qa/'cutouts.png')
