"""Offline, resumable action preparation; originals are never changed."""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
SOURCE = Path('C:/Users/meursault/Desktop/desktop-pet/图片')
GENERATOR = Path('C:/Users/meursault/.codex/skills/shengtu-skill/scripts/generate_image.py')
NEW = [
 ('stretch','伸懒腰','日常','arms slowly raised overhead, stretch upward, lean gently, relax arms'),
 ('leap','跳跃','互动','bend knees, push off, airborne arms spread, land softly, stand'),
 ('smile','开心闭眼微笑','情绪','neutral, cheeks lift, eyes close smiling, happy smile, reopen eyes'),
 ('shy','害羞','情绪','notice viewer, blush, hands near cheeks, look down shyly, recover'),
 ('angry','生气跺脚','情绪','frown, clench little fists, lift one foot, stamp foot, pout'),
 ('sad','失败沮丧','情绪','notice failure, shoulders slump, ears droop, head down, slow recovery'),
 ('wait','等待','日常','hands behind back, look left, look right, slight head tilt, return'),
 ('work','工作','日常','sit at tiny laptop, hands approach keyboard, type, pause thinking, type'),
 ('tea','喝茶','日常','hold teacup low, lift cup, sip, lower cup, contented expression'),
 ('yawn','打哈欠','日常','sleepy eyes, hand to mouth, mouth opens yawning, closes, relax'),
 ('files','查看文件','日常','hold blue folder, open folder, look down reading, turn page, close folder'),
 ('celebrate','庆祝','情绪','excited smile, raise fists, both arms up, happy bounce, relax'),
 ('comb','梳头','日常','hold small comb, bring to side hair, comb downward, second stroke, lower hand'),
 ('dress','整理衣服','日常','look down, gently smooth skirt left, smooth skirt right, adjust bow, stand'),
 ('affection','撒娇','互动','hands together, tilt head left, lean sweetly toward viewer, tilt right, smile'),
 ('curious','好奇查看','互动','notice something, lean forward, tilt head, peer closely, return'),
 ('afraid','害怕','情绪','startle, ears back, hands near chest, crouch slightly scared, recover'),
 ('clicked','被点击反应','互动','surprised blink, ears perk, little recoil, smile toward viewer, return'),
 ('dragged','拖动反应','互动','feet dangling as lifted, surprised face, arms spread for balance, sway left, sway right'),
 ('read','看书','日常','hold the blue spellbook from the supplied reading reference, open book, look down reading, lift one page, turn page, continue reading'),
]
EXISTING = [
 ('blink','眨眼','待机动作/眨眼','日常'),
 ('roll-front','向前打滚','打滚动作/向前','互动'),
 ('roll-left','向左打滚','打滚动作/向左','互动'),
 ('roll-right','向右打滚','打滚动作/向右','互动'),
 ('sleep','睡觉','睡眠动作','日常'),
 ('folder-sleep','靠文件夹睡觉','靠文件夹睡觉动作','日常'),
 ('screen','口袋电子屏幕','口袋电子屏幕动作','日常'),
 ('eat','进食','eating','日常'),
]

def extract(im, chroma=False):
    im = im.convert('RGBA')
    im.thumbnail((512,512), Image.Resampling.LANCZOS)
    a = np.array(im)
    if a[:,:,3].min() < 250:
        return im
    if chroma:
        rgb = a[:,:,:3].astype(float)
        # Remove green-screen and its antialiasing fringe, without touching blue dress.
        excess = rgb[:,:,1] - np.maximum(rgb[:,:,0],rgb[:,:,2])
        a[:,:,3] = np.clip((65-excess)*255/40,0,255).astype('uint8')
        a[:,:,1] = np.minimum(rgb[:,:,1],np.maximum(rgb[:,:,0],rgb[:,:,2])+20).astype('uint8')
    else:
        h,w=a.shape[:2]
        mask=np.zeros((h,w),np.uint8)
        cv2.setRNGSeed(123)
        cv2.grabCut(a[:,:,:3][:,:,::-1].copy(),mask,(3,3,w-6,h-6),np.zeros((1,65)),np.zeros((1,65)),4,cv2.GC_INIT_WITH_RECT)
        matte=((mask==1)|(mask==3)).astype('uint8')
        n,labels,stats,_=cv2.connectedComponentsWithStats(matte)
        if n<2: raise ValueError('No character extracted')
        keep=np.where(stats[:,cv2.CC_STAT_AREA]>max(25,stats[1:,cv2.CC_STAT_AREA].max()*.004))[0]
        keep=keep[keep!=0]
        a[:,:,3]=np.isin(labels,keep).astype('uint8')*255
    a[a[:,:,3]==0]=0
    return Image.fromarray(a)

def export(action_id,name,category,images,origin,paths):
    out=ROOT/'assets/actions'/action_id
    out.mkdir(parents=True,exist_ok=True)
    boxes=[im.getbbox() for im in images]
    if not all(boxes): raise ValueError(f'Empty frame: {name}')
    # One sequence-wide scale; never stretch each pose to the same height.
    left=min(b[0] for b in boxes);top=min(b[1] for b in boxes)
    right=max(b[2] for b in boxes);bottom=max(b[3] for b in boxes)
    width=right-left;height=bottom-top
    factor=min(220/width,222/height)
    frames=[]
    for i,(im,b) in enumerate(zip(images,boxes)):
        sprite=im.crop(b)
        sprite=sprite.resize((max(1,round(sprite.width*factor)),max(1,round(sprite.height*factor))),Image.Resampling.LANCZOS)
        canvas=Image.new('RGBA',(256,256))
        canvas.alpha_composite(sprite,(round((256-width*factor)/2+(b[0]-left)*factor),round(244-height*factor+(b[1]-top)*factor)))
        canvas.save(out/f'{i+1:02d}.png')
        frames.append(canvas)
    columns=4; rows=(len(frames)+3)//4
    atlas=Image.new('RGBA',(1024,rows*256))
    for i,frame in enumerate(frames): atlas.alpha_composite(frame,((i%4)*256,(i//4)*256))
    atlas.save(out/'atlas.png')
    frames[0].save(out/'poster.png')
    duration=140 if 'roll' in action_id else 220 if origin=='generated' else 190
    durations=[duration]*len(frames)
    durations[0]=400;durations[-1]=450
    if action_id in ('sleep','folder-sleep'): durations=[350]*len(frames)
    qa=ROOT/'qa/actions';qa.mkdir(parents=True,exist_ok=True)
    sheet=Image.new('RGB',atlas.size,'#48505e');sheet.paste(atlas,mask=atlas.getchannel('A'));sheet.save(qa/f'{action_id}.jpg')
    previews=[]
    for frame in frames:
        bg=Image.new('RGB',(256,256),'#48505e');bg.paste(frame,mask=frame.getchannel('A'));previews.append(bg)
    previews[0].save(qa/f'{action_id}.gif',save_all=True,append_images=previews[1:],duration=durations,loop=0)
    reviewed=(ROOT/'action-work'/action_id/'reviewed.txt').exists()
    return dict(id=action_id,name=name,category=category,origin=origin,frames=len(frames),columns=4,cell=256,durations=durations,atlas=f'actions/{action_id}/atlas.png',poster=f'actions/{action_id}/poster.png',sources=paths,review=('首轮静帧检查通过 · 六关键帧' if reviewed else '待人工验收') if origin=='generated' else '已转换')

def generate(item):
    action_id,name,category,motion=item
    raw=ROOT/'action-work'/action_id;raw.mkdir(parents=True,exist_ok=True)
    prompt=('Create exactly ONE sprite animation contact sheet, 3 columns by 2 rows, SIX equal square cells, reading left to right then top to bottom. '
      'Use the reference character exactly: white long hair, white cat ears, BLUE eyes, blue dress and blue Mary Jane shoes, snowflake clip on viewer RIGHT. '
      'Keep chibi proportions, face, costume, colors, lighting and linework IDENTICAL in all six frames. Full body in every cell, generous empty margin, same camera and scale. '
      'Flat pure bright green #00ff00 background in every cell, NO checkerboard, NO shadows, NO grid lines, NO text or numbers. '
      f'Action is {name}. Six consecutive KEY POSES including the beginning and return/recovery: {motion}. '
      'Do not draw six identical poses. No duplicates of the character within a cell. Do not crop ears, hands, hair, props or feet. Reference turnaround is identity guidance, not a pose to copy.')
    (raw/'prompt.txt').write_text(prompt,encoding='utf-8')
    target=raw/'raw.png'
    if not target.exists():
        extra=['--image',str(SOURCE/'待机动作/看书/pose_08_blue_spellbook.png')] if action_id=='read' else []
        result=subprocess.run([sys.executable,str(GENERATOR),'--provider','gpt','--mode','edit','--prompt',prompt,'--image',str(SOURCE/'参考图.png'),'--image',str(SOURCE/'三视图.png'),*extra,'--size','1536x1024','--out',str(target)],capture_output=True,text=True,encoding='utf-8',errors='replace')
        if result.returncode or not target.exists():
            print(f'FAILED {action_id}: {result.stdout[-500:]} {result.stderr[-500:]}',flush=True)
            return None
    im=Image.open(target)
    cells=[im.crop((round(c*im.width/3),round(r*im.height/2),round((c+1)*im.width/3),round((r+1)*im.height/2))) for r in range(2) for c in range(3)]
    result=export(action_id,name,category,[extract(cell,True) for cell in cells],'generated',[str(target)])
    print(f'GENERATED {name}',flush=True)
    return result

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--generate',action='store_true');parser.add_argument('--only');args=parser.parse_args()
    manifest=ROOT/'assets/actions/catalog.json'
    catalog=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
    if not args.generate:
        for action_id,name,folder,category in EXISTING:
            paths=sorted((SOURCE/folder).glob('*.png'))
            if action_id in ('roll-front','roll-right'):
                paths=paths[1:]  # First input is a 3x3 overview, not an animation frame.
            result=export(action_id,name,category,[extract(Image.open(p)) for p in paths],'existing',[str(p) for p in paths])
            if action_id=='folder-sleep':result['review']='原图道具与姿势差异较大，待精修'
            catalog=[a for a in catalog if a['id']!=action_id]+[result]
            manifest.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
            print(f'CONVERTED {name}: {len(paths)} frames',flush=True)
        for i,p in enumerate(sorted((SOURCE/'sit').glob('*.png'))+sorted((SOURCE/'待机动作/看书').glob('*.png'))):
            action_id=f'reading-pose-{i+1}'
            result=export(action_id,f'阅读姿势 {i+1}','静态姿势',[extract(Image.open(p))],'existing',[str(p)])
            result['review']='静态素材，非完整动作'
            catalog=[a for a in catalog if a['id']!=action_id]+[result]
        manifest.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        items=[item for item in NEW if not args.only or item[0]==args.only]
        with ThreadPoolExecutor(max_workers=2) as pool:
            for result in pool.map(generate,items):
                if result:
                    # Other preparation passes may add original sequences while generation runs.
                    catalog=json.loads(manifest.read_text(encoding='utf-8')) if manifest.exists() else []
                    catalog=[a for a in catalog if a['id']!=result['id']]+[result]
                    manifest.parent.mkdir(parents=True,exist_ok=True)
                    manifest.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    public=ROOT/'frontend/public/actions'
    import shutil
    shutil.copytree(ROOT/'assets/actions',public,dirs_exist_ok=True)

if __name__=='__main__': main()
