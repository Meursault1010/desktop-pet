"""Assemble clean recovery drawings at one scale and one ground line; no flow."""
import json,math
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'output/dance-rest-20261023'
ID='dance-rest'

def cutout(path):
    a=np.array(Image.open(path).convert('RGBA'))
    rgb=a[:,:,:3].astype(float)
    excess=rgb[:,:,1]-np.maximum(rgb[:,:,0],rgb[:,:,2])
    weight=np.clip(1-(excess-12)/65,0,1)
    a[:,:,3]=np.uint8(a[:,:,3]*weight)
    edge=(weight>0)&(weight<1)
    a[:,:,1][edge]=np.minimum(a[:,:,1][edge],np.maximum(a[:,:,0][edge],a[:,:,2][edge]))
    count,labels,stats,_=cv2.connectedComponentsWithStats(np.uint8(a[:,:,3]>24))
    keep=np.zeros(a.shape[:2],np.uint8)
    if count<=1:raise ValueError(f'No character found: {path}')
    largest=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
    keep[labels==largest]=1
    keep=cv2.dilate(keep,np.ones((3,3),np.uint8))
    a[keep==0]=0
    a[a[:,:,3]<4]=0
    image=Image.fromarray(a)
    return image.resize((256,256),Image.Resampling.LANCZOS)

def main():
    folder=ROOT/'assets/actions'/ID;folder.mkdir(exist_ok=True,parents=True)
    cells=[];metrics=[]
    for index in range(1,11):
        if index==1:
            dance=next(a for a in json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8')) if a['id']=='music-waltz')
            last=dance['frames']-1;x=last%dance['columns']*256;y=last//dance['columns']*256
            with Image.open(ROOT/'assets/actions/music-waltz/atlas.png') as atlas:cell=atlas.crop((x,y,x+256,y+256)).convert('RGBA')
            cell.save(OUT/'01-runtime.png')
        else:cell=cutout(OUT/f'{index:02d}-raw.png')
        a=np.array(cell);ys,xs=np.where(a[:,:,3]>64)
        if not len(ys):raise RuntimeError(f'Empty frame {index}')
        # Translation only: never resize sitting art to standing height.
        dy=0 if index==1 else 231-int(ys.max())
        normalized=cell.copy() if index==1 else Image.new('RGBA',(256,256))
        if index!=1:normalized.alpha_composite(cell,(0,dy))
        normalized.save(folder/f'{index:02d}.png');cells.append(normalized)
        box=normalized.getbbox();metrics.append({'frame':index,'bbox':box,'ground_shift':dy})
    atlas=Image.new('RGBA',(5*256,2*256))
    for i,cell in enumerate(cells):atlas.paste(cell,(i%5*256,i//5*256))
    atlas.save(folder/'atlas.png');cells[7].save(folder/'poster.png')
    entry=[350,500,450,280,300,300,350,650,650,130]
    action=dict(id=ID,name='舞后坐下休息',category='坐下待机',idle_state='sit',idle_automatic=False,origin='generated',frames=10,columns=5,cell=256,
        durations=entry,atlas=f'actions/{ID}/atlas.png',poster=f'actions/{ID}/poster.png',
        authored_motion=True,grounded_pose=True,dance_rest=True,baseline=328/360,
        interpolation='none',optical_flow=False,review='Generated individual recovery drawings, fixed ground and scale',
        sources=[str(OUT/('01-runtime.png' if i==1 else f'{i:02d}-raw.png')) for i in range(1,11)])
    path=ROOT/'assets/actions/catalog.json';catalog=json.loads(path.read_text(encoding='utf-8'))
    catalog=[a for a in catalog if a['id']!=ID]+[action]
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    web=ROOT/'frontend/public/actions'/ID;web.mkdir(exist_ok=True,parents=True)
    atlas.save(web/'atlas.webp',lossless=True,method=3,exact=True);cells[7].save(web/'poster.webp',lossless=True,method=3,exact=True)
    path=ROOT/'frontend/public/actions/catalog.json';catalog=json.loads(path.read_text(encoding='utf-8'))
    catalog=[a for a in catalog if a['id']!=ID]+[dict(action,atlas=f'actions/{ID}/atlas.webp',poster=f'actions/{ID}/poster.webp')]
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    config_path=ROOT/'assets/actions/idle-states.json'
    config=json.loads(config_path.read_text(encoding='utf-8'))
    sitting=next(state for state in config['states'] if state['id']=='sit')
    if ID not in sitting['actions']:sitting['actions'].append(ID)
    sitting['roles'][ID]='舞后恢复与坐姿呼吸'
    for target in (config_path,ROOT/'frontend/public/actions/idle-states.json'):
        payload=(json.dumps(config,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        with target.open('r+b') as handle:
            handle.write(payload)
            handle.truncate()
    board=Image.new('RGB',(1280,560),'#cedfee');draw=ImageDraw.Draw(board)
    for i,cell in enumerate(cells):
        x=i%5*256;y=i//5*280;board.paste(cell,(x,y+24),cell);draw.text((x+5,y+4),f'{i+1:02d}',fill='#203b50')
    board.save(OUT/'review.jpg',quality=95)
    (OUT/'build-report.json').write_text(json.dumps({'action':ID,'frames':metrics,'optical_flow':False},indent=2),encoding='utf-8')
    print('Installed',ID,'10 clean keyframes')
if __name__=='__main__':main()
