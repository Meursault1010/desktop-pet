"""Publish visually reviewed compact reaches with remeasured palm centers."""
from pathlib import Path
import json
from PIL import Image
from statistics import median


def chroma_cutout(cell):
    cell=cell.convert('RGBA')
    samples=[cell.getpixel((x,y))[:3] for x,y in
             ((2,2),(509,2),(2,509),(509,509),(256,2),(2,256),(509,256),(256,509))]
    key=tuple(median(c[i] for c in samples) for i in range(3))
    strength=key[1]-max(key[0],key[2])
    pixels=[]
    for r,g,b,_ in cell.getdata():
        alpha=max(0,min(1,1-max(g-max(r,b)-7,0)/max(1,strength-7)))
        if alpha<.08:pixels.append((0,0,0,0));continue
        rgb=tuple(round(max(0,min(255,(v-k*(1-alpha))/alpha))) for v,k in zip((r,g,b),key))
        pixels.append((*rgb,round(alpha*255)))
    cell.putdata(pixels)
    return cell

root=Path(__file__).resolve().parent
work=root/'action-work/short-arm-drag'
sheet=Image.open(work/'generated.png').convert('RGBA')
if sheet.size!=(1536,1024):raise ValueError('Unexpected sprite layout')
hands={'upper-left':(252,214),'up':(244,148),'upper-right':(312,206),
       'left':(165,181),'down':(212,280),'right':(270,222)}
meta={}
review=Image.new('RGBA',(768,512),'#24334a')
for i,(name,hand) in enumerate(hands.items()):
    cell=sheet.crop((i%3*512,i//3*512,i%3*512+512,i//3*512+512))
    sprite=chroma_cutout(cell).resize((256,256),Image.Resampling.LANCZOS)
    sprite.save(root/f'assets/drag-resist/{name}.png')
    meta[name]={'hand':[hand[0]/2,hand[1]/2]}
    review.alpha_composite(sprite,(i%3*256,i//3*256))
(root/'assets/drag-resist/poses.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
review.save(work/'review.png')
