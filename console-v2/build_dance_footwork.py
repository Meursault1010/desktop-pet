"""Analyze actual shoe contacts; derive displacement from planted-foot constraints."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'output/dance-no-flow-20261023'
ASSETS=ROOT/'assets/actions/music-waltz'


def contacts(image):
    a=np.array(image.convert('RGBA'))
    mask=a[:,:,3]>128
    ys,xs=np.where(mask)
    if not len(ys):return []
    floor=int(ys.max())
    # Sole observations are measured on actual visible pixels, not pose centers.
    sole=np.uint8(mask & (np.indices(mask.shape)[0]>=floor-2))
    count,labels,stats,_=cv2.connectedComponentsWithStats(sole)
    result=[]
    for k in range(1,count):
        if stats[k,cv2.CC_STAT_AREA]<3:continue
        yy,xx=np.where(labels==k)
        result.append([float(np.median(xx)),float(np.max(yy))])
    return sorted(result)


def main(source=None):
    OUT.mkdir(exist_ok=True,parents=True)
    source=source or OUT
    report=json.loads((source/'build-report.json').read_text())
    if report.get('optical_flow') is not False or report.get('interpolation')!='none':
        raise ValueError('Rebuild original drawings first; interpolated dance assets are disabled')
    atlas=Image.open(source/'atlas.png').convert('RGBA')
    observations=[]
    for i in range(report['frames']):
        x=i%report['columns']*256;y=i//report['columns']*256
        observations.append(contacts(atlas.crop((x,y,x+256,y+256))))
    root=np.zeros(2);prev=None;support=0;rows=[];switches=[]
    for i,points in enumerate(observations):
        if not points:raise RuntimeError(f'No foot at {i}')
        if prev is None:
            point=points[0]
        else:
            point=min(points,key=lambda p:np.linalg.norm(np.array(p)-prev))
            delta=prev-np.array(point)
            # A newly planted, distant foot takes over at the CURRENT root position.
            if np.linalg.norm(delta)>8:
                support+=1;switches.append(i)
            else:root+=delta*160/256
        rows.append({'frame':i,'root':[float(v) for v in root], 'contact':point,'support':support,'candidates':points})
        prev=np.array(point)
    summary={'frames':len(rows),'support_changes':len(switches),'switches':switches,'root_min':np.min([r['root'] for r in rows],axis=0).tolist(),'root_max':np.max([r['root'] for r in rows],axis=0).tolist(),'net':rows[-1]['root'],'rows':rows}
    (OUT/'contact-analysis.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print({k:v for k,v in summary.items() if k!='rows'},flush=True)
    sheet=Image.new('RGB',(1280,((len(report['transitions'])+7)//8)*180),'#cedfee');draw=ImageDraw.Draw(sheet)
    n=0
    for i,t in enumerate(report['transitions']):
        x=n%report['columns']*256;y=n//report['columns']*256
        im=atlas.crop((x,y,x+256,y+256)).resize((160,160))
        bx=i%8*160;by=i//8*180;sheet.paste(im,(bx,by+20),im)
        draw.text((bx+2,by+2),f'{i+1}: f{n}',fill='#203b50')
        for px,py in observations[n]:draw.ellipse((bx+px*.625-2,by+20+py*.625-2,bx+px*.625+2,by+20+py*.625+2),fill='red')
        n+=t['samples']
    sheet.save(OUT/'contact-observations.jpg',quality=94)
    # Retrace the same physical steps: reversing both images and support track
    # closes the route without distributing a sliding correction over the clip.
    order=list(range(len(rows)))+list(range(len(rows)-2,0,-1))
    count=len(order);columns=10
    baked=Image.new('RGBA',(columns*256,((count+columns-1)//columns)*256))
    for slot,index in enumerate(order):
        x=index%report['columns']*256;y=index//report['columns']*256
        baked.paste(atlas.crop((x,y,x+256,y+256)),(slot%columns*256,slot//columns*256))
    baked.save(ASSETS/'atlas.png',optimize=False)
    durations=[report['durations'][index] for index in order]
    # A short planted pause at each direction change avoids a velocity snap.
    durations[0]+=150;durations[len(rows)-1]+=150
    track={'version':1,'cell_scale':160/256,'frames':count,
           'loop':'forward-and-return','source_frames':len(rows),
           'bounds':[summary['root_min'],summary['root_max']],
           'rows':[dict(rows[index],frame=slot,source_frame=index) for slot,index in enumerate(order)]}
    (ASSETS/'footwork.json').write_text(json.dumps(track,separators=(',',':')),encoding='utf-8')
    report.update(frames=count,columns=columns,durations=durations,duration_seconds=sum(durations)/1000,
                  footwork='sole contact lock; forward-and-return; fixed scale',source_frames=len(rows))
    (ASSETS/'choreography.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    path=ROOT/'assets/actions/catalog.json'
    catalog=json.loads(path.read_text(encoding='utf-8'))
    action=next(a for a in catalog if a['id']=='music-waltz')
    action.update(frames=count,columns=columns,durations=durations,
                  review='Original drawings only; no optical flow or morphing; foot-driven forward and return',footwork=True)
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    from export_dance_pages import export
    export()
    print('Installed footwork:',count,'frames,',sum(durations)/1000,'seconds',flush=True)

if __name__=='__main__':main()
