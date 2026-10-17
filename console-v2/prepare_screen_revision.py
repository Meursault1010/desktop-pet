"""Split and chroma-key reviewed 3x4 sheet, preserving pose coordinates."""
import json
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
from screen_revision import OUT

NAMES=['接近口袋','伸入口袋','抽出一半','完全取出','抬起点亮','持屏查看','手指靠近','点击屏幕','点击后抬指','滑动操作','再次点击','保持查看']

def main():
    raw=Image.open(OUT/'raw.png').convert('RGB')
    frames=[]
    original=OUT/'原始分帧';original.mkdir(exist_ok=True)
    clean=OUT/'透明静帧';clean.mkdir(exist_ok=True)
    for i in range(12):
        x,y=i%3,i//3
        cell=raw.crop((round(x*raw.width/3),round(y*raw.height/4),round((x+1)*raw.width/3),round((y+1)*raw.height/4)))
        cell.save(original/f'frame_{i+1:02d}.png')
        rgb=np.array(cell).astype(float)
        excess=rgb[:,:,1]-np.maximum(rgb[:,:,0],rgb[:,:,2])
        alpha=np.clip((65-excess)*255/40,0,255)
        # Generator added white gutters: remove only white components connected
        # to cell edges; never remove the disconnected white hair or skin.
        white=((rgb.min(axis=2)>230)&((rgb.max(axis=2)-rgb.min(axis=2))<18)).astype('uint8')
        _,labels=cv2.connectedComponents(white)
        border=np.unique(np.concatenate((labels[0],labels[-1],labels[:,0],labels[:,-1])))
        border=border[border!=0]
        alpha[np.isin(labels,border)]=0
        # Decontaminate only keyed edge pixels, not opaque dress/skin colors.
        edge=(alpha>0)&(alpha<255)
        rgb[:,:,1][edge]=np.minimum(rgb[:,:,1][edge],np.maximum(rgb[:,:,0][edge],rgb[:,:,2][edge])+15)
        rgba=np.dstack((rgb,alpha)).clip(0,255).astype('uint8')
        count,parts,stats,_=cv2.connectedComponentsWithStats((rgba[:,:,3]>0).astype('uint8'))
        if count<2:raise ValueError('Empty character extraction')
        largest=1+np.argmax(stats[1:,cv2.CC_STAT_AREA])
        rgba[:,:,3][parts!=largest]=0
        rgba[rgba[:,:,3]==0]=0
        frame=Image.fromarray(rgba)
        frame.save(clean/f'frame_{i+1:02d}.png');frames.append(frame)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
    sheet=Image.new('RGB',(1200,1680),'#303b4c');draw=ImageDraw.Draw(sheet)
    previews=[]
    for i,frame in enumerate(frames):
        thumb=frame.resize((380,380),Image.Resampling.LANCZOS)
        x,y=i%3*400,i//3*420
        sheet.paste(thumb,(x+10,y),thumb)
        draw.text((x+15,y+387),f'{i+1:02d}  {NAMES[i]}',font=font,fill='#dbeafe')
        bg=Image.new('RGB',frame.size,'#303b4c');bg.paste(frame,mask=frame.getchannel('A'));previews.append(bg)
    sheet.save(OUT/'静帧总览.jpg',quality=94)
    durations=[350,180,180,240,250,550,180,180,200,300,180,700]
    previews[0].save(OUT/'完整动作预览.gif',save_all=True,append_images=previews[1:],duration=durations,loop=0)
    # The operating loop starts only AFTER retrieval: the device stays held.
    operating=[5,6,7,8,9,10,11,5]
    previews[5].save(OUT/'持屏操作循环.gif',save_all=True,append_images=[previews[i] for i in operating[1:]],duration=[550,180,180,200,300,180,700,250],loop=0)
    (OUT/'sequence.json').write_text(json.dumps({'canvas':frames[0].size,'frames':[{'file':f'透明静帧/frame_{i+1:02d}.png','pose':name,'duration_ms':durations[i]} for i,name in enumerate(NAMES)],'intro_frames':[1,2,3,4,5],'operating_loop_frames':[6,7,8,9,10,11,12,6],'notes':'取出与抬起时双手接住屏幕，操作段由固定一只手托屏、另一只手点击；不应把完整取出过程无限循环。'},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Exported twelve original crops, twelve transparent stills, contact sheet and two GIF previews.')

if __name__=='__main__':main()
