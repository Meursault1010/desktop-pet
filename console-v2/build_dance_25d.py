"""Reorder approved dance drawings; install unwarped, frame-by-frame animation."""
import argparse
import json
import math
from pathlib import Path
import shutil
import cv2
import numpy as np
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'output/waltz-20261020'
BRIDGES=ROOT.parent/'output/dance-25d-20261023'
OUT=ROOT.parent/'output/dance-no-flow-20261023'
RUNTIME=ROOT/'assets/actions/music-waltz'


def inputs():
    report=json.loads((SOURCE/'yuki-waltz-consistent-mixed-report.json').read_text())
    names=list(dict.fromkeys(k['file'] for k in report['keys']))
    return names,[np.array(Image.open(SOURCE/'consistent-keys'/name).convert('RGBA')) for name in names]


def distances(poses):
    thumbs=np.array([cv2.resize(a,(80,90),interpolation=cv2.INTER_AREA).astype(np.float32)/255 for a in poses])
    alpha=thumbs[:,:,:,3]
    color=thumbs[:,:,:,:3]*alpha[:,:,:,None]+.9*(1-alpha[:,:,:,None])
    # Balance the hands and feet against the visually dominant head/hair.
    weight=np.ones((90,80),np.float32)
    weight[:37]=.65;weight[40:67]=1.6;weight[67:]=2.2
    edges=np.array([cv2.distanceTransform(np.uint8(a<.3),cv2.DIST_L2,3) for a in alpha])
    # Explicit viewing angles prevent pale back hair being mistaken for a front face.
    angles=np.zeros(len(poses))
    authored={6:-25,13:-25,14:-85,15:-60,16:-50,28:-45,33:-45,34:-90,
              35:-135,36:-160,37:-180,38:165,39:135,40:90,41:45,
              42:-35,43:-30,44:-40,47:-35,53:180,54:22.5}
    for index,angle in authored.items():
        if index<=len(poses):angles[index-1]=angle
    d=np.zeros((len(poses),len(poses)))
    for i in range(len(poses)):
        for j in range(i):
            mask=np.maximum(alpha[i],alpha[j])>.1
            rgb=np.sqrt(((color[i]-color[j])**2).sum(2))
            shape=np.abs(alpha[i]-alpha[j])
            chamfer=(edges[i]*alpha[j]+edges[j]*alpha[i])/12
            angular=abs(angles[i]-angles[j]);angular=min(angular,360-angular)/180
            d[i,j]=d[j,i]=float(((rgb*.45+shape*.4+chamfer*.15)*weight)[mask].mean())+.65*angular
    return d


def optimize(d):
    n=len(d);rng=np.random.default_rng(20261023)
    cost=d**4
    best=None;best_value=float('inf')
    candidates=[list(range(n))]
    for start in range(n):
        order=[start];remaining=set(range(n))-{start}
        while remaining:
            next_=min(remaining,key=lambda j:d[order[-1],j])
            order.append(next_);remaining.remove(next_)
        candidates.append(order)
    for _ in range(60):
        candidates.append(rng.permutation(n).tolist())
    for order in candidates:
        changed=True
        while changed:
            changed=False
            for i in range(n-2):
                a,b=order[i],order[i+1]
                for k in range(i+2,n):
                    if i==0 and k==n-1:continue
                    c,e=order[k],order[(k+1)%n]
                    if cost[a,c]+cost[b,e]<cost[a,b]+cost[c,e]-1e-12:
                        order[i+1:k+1]=reversed(order[i+1:k+1]);changed=True
                        break
                if changed:break
        value=sum(cost[a,b] for a,b in zip(order,order[1:]+order[:1]))
        if value<best_value:best_value,best=value,order[:]
    # Start with the familiar front-standing pose; preserve a closed cycle.
    k=best.index(0)
    return best[k:]+best[:k]


def contact(poses,names,order):
    sheet=Image.new('RGB',(8*160,math.ceil(len(order)/8)*195),'#cedfee')
    draw=ImageDraw.Draw(sheet)
    for k,i in enumerate(order):
        im=Image.fromarray(poses[i]).resize((160,180),Image.Resampling.LANCZOS)
        x,y=k%8*160,k//8*195
        sheet.paste(im,(x,y+15),im)
        draw.text((x+3,y+1),f'{k+1:02d}: source {i+1:02d}',fill='#203b50')
    sheet.save(OUT/'ordered-poses.jpg',quality=94)


def clean_cell(pose):
    # Only the original deterministic padding and uniform downsampling remain.
    local=Image.new('RGBA',(360,360))
    local.alpha_composite(Image.fromarray(pose),(20,0))
    return local.resize((256,256),Image.Resampling.LANCZOS)


def bake(names,poses,order,d,report):
    import hashlib
    RUNTIME.mkdir(exist_ok=True,parents=True)
    atlas=Image.new('RGBA',(10*256,math.ceil(len(order)/10)*256))
    durations=[];transitions=[];checks=[]
    for slot,index in enumerate(order):
        following=order[(slot+1)%len(order)]
        cell=clean_cell(poses[index])
        atlas.paste(cell,(slot%10*256,slot//10*256))
        # Authored drawings, not repeated copies presented as 60 unique fps.
        duration=int(np.clip(90+180*d[index,following],100,170))
        durations.append(duration)
        transitions.append({'from':names[index],'to':names[following],
                            'samples':1,'duration_ms':duration,'score':float(d[index,following])})
        checks.append({'frame':slot,'source':names[index],
                       'cell_sha256':hashlib.sha256(cell.tobytes()).hexdigest()})
    atlas.save(OUT/'atlas.png',optimize=False)
    atlas.crop((0,0,256,256)).save(OUT/'poster.png')
    report.update(frames=len(order),columns=10,durations=durations,
                  duration_seconds=sum(durations)/1000,transitions=transitions,
                  loop_closed=True,interpolation='none',optical_flow=False,
                  silhouette_morph=False,frame_checks=checks)
    (OUT/'build-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    shutil.copy2(OUT/'poster.png',RUNTIME/'poster.png')
    catalog_path=ROOT/'assets/actions/catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    action=next(a for a in catalog if a['id']=='music-waltz')
    action.update(authored_motion=True,spatial_dance=True,baseline=328/360,
                  interpolation='none',optical_flow=False,
                  tempo_profile='authored drawings with variable holds')
    catalog_path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    from build_dance_footwork import main as build_footwork
    build_footwork(source=OUT)
    print('Installed original drawings; optical flow and image morphing disabled',flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--order-only',action='store_true');args=parser.parse_args()
    cv2.setNumThreads(1);OUT.mkdir(exist_ok=True,parents=True)
    names,poses=inputs();d=distances(poses);order=optimize(d)
    def stats(seq):
        jumps=[float(d[a,b]) for a,b in zip(seq,seq[1:]+seq[:1])]
        return {'maximum':max(jumps),'mean':float(np.mean(jumps)),'fourth_power_sum':sum(v**4 for v in jumps)}
    ranked=sorted([(float(d[a,b]),names[a],names[b]) for a,b in zip(order,order[1:]+order[:1])],reverse=True)
    generated=BRIDGES/'generated-bridges.json'
    if generated.exists():
        for item in json.loads(generated.read_text()):
            path=BRIDGES/item['file']
            if not item['success'] or not path.exists():continue
            index=names.index(item['from'])
            slot=order.index(index)+1
            order.insert(slot,len(poses))
            names.append(item['file']);poses.append(np.array(Image.open(path).convert('RGBA')))
        if len(poses)>len(d):
            d=distances(poses)
    ranked=sorted([(float(d[a,b]),names[a],names[b]) for a,b in zip(order,order[1:]+order[:1])],reverse=True)
    report={'source_count':52,'originals_used':len(set(order)&set(range(52))),'used_count':len(order),'order':[names[i] for i in order],
            'before':stats(list(range(52))),'after':stats(order),'largest_pairs':ranked[:10],
            'method':'deterministic multistart nearest-neighbor + fourth-power 2-opt closed cycle'}
    (OUT/'order-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    contact(poses,names,order)
    print(json.dumps(report,indent=2),flush=True)
    if not args.order_only:
        bake(names,poses,order,d,report)


if __name__=='__main__':main()
