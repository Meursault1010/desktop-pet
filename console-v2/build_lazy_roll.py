"""Publish reviewed lazy rolls at the same RGBA resolution as other actions."""
import argparse
import json
import shutil
from PIL import Image, ImageDraw
from build_ground_idle import cutout
from generate_ground_idle import ROOT
from generate_lazy_roll import WORK, SPECS

def prepare(key, publish=False):
    # The independently generated away sheet changes perspective at frame 3.
    # Reverse the accepted axial turn to preserve the same camera and identity.
    source_key = 'lazy-roll-toward'
    sheet = Image.open(WORK/source_key/'raw.png').convert('RGBA')
    fg = lambda pixel: pixel[1]-max(pixel[0],pixel[2]) < 70
    counts = [sum(map(fg,sheet.crop((0,y,sheet.width,y+1)).getdata())) for y in range(sheet.height)]
    rows = [0]
    for boundary in (sheet.height/3,2*sheet.height/3):
        rows.append(min(range(round(boundary)-70,round(boundary)+71),
                        key=lambda y:(sum(counts[y-3:y+4]),abs(y-boundary))))
    rows.append(sheet.height)
    cells=[]
    for r in range(3):
        counts_x=[sum(map(fg,sheet.crop((x,rows[r],x+1,rows[r+1])).getdata())) for x in range(sheet.width)]
        columns=[0]
        for boundary in (sheet.width/4,sheet.width/2,3*sheet.width/4):
            columns.append(min(range(round(boundary)-70,round(boundary)+71),
                               key=lambda x:(sum(counts_x[x-3:x+4]),abs(x-boundary))))
        columns.append(sheet.width)
        cells.extend(cutout(sheet.crop((columns[c],rows[r],columns[c+1],rows[r+1]))) for c in range(4))
    scale=min(224/max(b[2]-b[0] for _,b in cells),200/max(b[3]-b[1] for _,b in cells))
    frames=[]
    for cell,bbox in cells:
        sprite=cell.crop(bbox)
        # Match the other ground actions: one direct high-quality resize,
        # original colours and soft alpha; no low-res intermediate or palette cap.
        sprite=sprite.resize((round(sprite.width*scale),round(sprite.height*scale)),Image.Resampling.LANCZOS)
        frame=Image.new('RGBA',(256,256))
        frame.alpha_composite(sprite,((256-sprite.width)//2,248-sprite.height))
        frames.append(frame)
    frames[-1]=frames[0].copy()  # Exact cycle closure, not merely a similar AI pose.
    if key.endswith('away'):
        frames = [frames[0]] + list(reversed(frames[1:-1])) + [frames[0].copy()]
    durations=[520,400,400,420,440,460,440,420,400,400,420,180]
    atlas=Image.new('RGBA',(1024,768))
    review=Image.new('RGB',(1024,840),'#24334a')
    draw=ImageDraw.Draw(review)
    previews=[]
    for i,frame in enumerate(frames):
        atlas.alpha_composite(frame,((i%4)*256,(i//4)*256))
        review.paste(frame,((i%4)*256,(i//4)*280),frame)
        draw.text(((i%4)*256+8,(i//4)*280+258),f'{key} / {i+1}',fill='white')
        bg=Image.new('RGB',(256,256),'#24334a');bg.paste(frame,mask=frame.getchannel('A'));previews.append(bg)
    review.save(WORK/key/'review.png')
    previews[0].save(WORK/key/'preview.gif',save_all=True,append_images=previews[1:],duration=durations,loop=0)
    if not publish:return
    if not (WORK/key/'reviewed.txt').exists():raise ValueError('Visual review required')
    out=ROOT/'assets/actions'/key;out.mkdir(parents=True,exist_ok=True)
    atlas.save(out/'atlas.png');frames[0].save(out/'poster.png')
    for i,frame in enumerate(frames):frame.save(out/f'{i+1:02d}.png')
    entry=dict(id=key,name=SPECS[key],category='待机',origin='generated',frames=12,columns=4,cell=256,
               durations=durations,atlas=f'actions/{key}/atlas.png',poster=f'actions/{key}/poster.png',
               sources=[str((WORK/source_key/'raw.png').relative_to(ROOT))],pixel_art=False,lazy_roll=True,
               end_posture='prone',review='已审查：纵轴侧滚，统一全彩柔和边缘，首尾一致')
    manifest=ROOT/'assets/actions/catalog.json'
    entries=json.loads(manifest.read_text(encoding='utf-8'))
    entries=[a for a in entries if a['id']!=key]+[entry]
    manifest.write_text(json.dumps(entries,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    shutil.copytree(out,ROOT/'frontend/public/actions'/key,dirs_exist_ok=True)
    shutil.copyfile(manifest,ROOT/'frontend/public/actions/catalog.json')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--publish',action='store_true');args=parser.parse_args()
    for key in SPECS:
        if (WORK/key/'raw.png').exists():prepare(key,args.publish);print(f'PREPARED {key}',flush=True)
