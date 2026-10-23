"""Build isolated autoplay sprites; never overwrite existing character artwork."""
import json
import shutil
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
WORK = ROOT/'action-work/autoplay'


def extract(im):
    """These sheets have neutral checkerboards and blue enclosing line art.

    GrabCut mistook white hair/ears for the background. Recover the closed
    colored silhouette first, retaining its white interior instead of cutting
    rectangular holes in the crown. Limited to this batch, not older assets.
    """
    rgba = np.array(im.convert('RGBA'))
    if rgba[:,:,3].min() < 250:
        return im.convert('RGBA')
    rgb = rgba[:,:,:3].astype(np.int16)
    colored = ((rgb.max(axis=2)-rgb.min(axis=2)) > 12).astype(np.uint8)*255
    outline = cv2.morphologyEx(colored,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    contours,_ = cv2.findContours(outline,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        raise ValueError('No colored silhouette in autoplay frame')
    matte = np.zeros(outline.shape,np.uint8)
    largest = max(cv2.contourArea(c) for c in contours)
    cv2.drawContours(matte,[c for c in contours if cv2.contourArea(c)>max(20,largest*.003)],-1,255,cv2.FILLED)
    rgba[:,:,3] = matte
    rgba[matte==0] = 0
    return Image.fromarray(rgba)


def cells(path, columns=4, rows=3):
    image = Image.open(path).convert('RGBA')
    # Generated rows are not exactly equal. Equal-thirds slicing cut the
    # third row's ears, breaking the enclosing line and losing white hair.
    row_edges = ([0,354,672,1024] if path.name == 'climb-keyframes.png' else
                 [0,350,650,1024]) if image.size == (1536,1024) and rows == 3 else [round(r*image.height/rows) for r in range(rows+1)]
    return [extract(image.crop((round(c*image.width/columns), row_edges[r],
                               round((c+1)*image.width/columns), row_edges[r+1])))
            for r in range(rows) for c in range(columns)]


def publish(key, name, images, durations, factor, reference=None, layout=None):
    folder = ROOT/'assets/actions'/key
    folder.mkdir(parents=True, exist_ok=True)
    boxes = [im.getbbox() for im in images]
    if not all(boxes):
        raise ValueError('Empty autoplay frame: '+key)
    ref = reference or boxes[0]
    left,top = min(b[0] for b in boxes),min(b[1] for b in boxes)
    right,bottom = max(b[2] for b in boxes),max(b[3] for b in boxes)
    factor = min(factor, 248/(right-left),248/(bottom-top))
    # One fixed scale and anchor per sequence. Never resize each silhouette.
    dx, dy = 128-(ref[0]+ref[2])/2*factor, 251-ref[3]*factor
    dx = max(3-left*factor,min(dx,253-right*factor))
    dy = max(3-top*factor,min(dy,253-bottom*factor))
    if layout is not None:
        factor,dx,dy = layout
    atlas = Image.new('RGBA', (1024, 256*((len(images)+3)//4)))
    frames = []
    for i, (im, box) in enumerate(zip(images, boxes)):
        sprite = im.crop(box)
        sprite = sprite.resize((round(sprite.width*factor), round(sprite.height*factor)), Image.Resampling.LANCZOS)
        x,y = round(box[0]*factor+dx), round(box[1]*factor+dy)
        if min(x,y) < 0 or x+sprite.width > 256 or y+sprite.height > 256:
            raise ValueError('Frame clipping: '+key+':'+str(i))
        frame = Image.new('RGBA',(256,256))
        frame.alpha_composite(sprite,(x,y))
        frame.save(folder/f'{i+1:02d}.png')
        atlas.alpha_composite(frame, (i%4*256,i//4*256))
        frames.append(frame)
    atlas.save(folder/'atlas.png')
    frames[0].save(folder/'poster.png')
    target = ROOT/'frontend/public/actions'/key
    target.mkdir(parents=True,exist_ok=True)
    for filename in ('atlas','poster'):
        Image.open(folder/(filename+'.png')).save(target/(filename+'.webp'),lossless=True,exact=True)
        (target/(filename+'.png')).unlink(missing_ok=True)
    return dict(id=key,name=name,category='自主玩耍',origin='generated',frames=len(frames),columns=4,
                cell=256,durations=durations,atlas=f'actions/{key}/atlas.png',poster=f'actions/{key}/poster.png',
                sources=['action-work/autoplay/keyframes.png'],review='本地抠图与尺寸检查；程序衔接',
                idle_automatic=False,autoplay_only=True,scale_calibrated=True)


def main():
    cv2.setNumThreads(1)
    source = cells(WORK/'keyframes.png')
    factor = 222/(source[0].getbbox()[3]-source[0].getbbox()[1])
    entries = [
        publish('play-peek','探身看看你',source[:4],[380,650,850,420],factor),
        publish('play-sit','坐着晃晃腿',source[4:8],[600,750,850,650],factor),
        publish('play-lean','靠近与站稳',source[8:12],[450,650,650,450],factor),
    ]
    if (WORK/'climb-keyframes.png').exists():
        climb = cells(WORK/'climb-keyframes.png')
        boxes = [im.getbbox() for im in climb]
        ref = boxes[0]
        left,top = min(b[0] for b in boxes),min(b[1] for b in boxes)
        right,bottom = max(b[2] for b in boxes),max(b[3] for b in boxes)
        climb_factor = min(222/(ref[3]-ref[1]),248/(right-left),248/(bottom-top))
        dx = max(3-left*climb_factor,min(128-(ref[0]+ref[2])/2*climb_factor,253-right*climb_factor))
        dy = max(3-top*climb_factor,min(251-ref[3]*climb_factor,253-bottom*climb_factor))
        layout = (climb_factor,dx,dy)
        entries += [publish('play-climb-up','抓稳后爬上图标',climb[:6],[400,550,650,650,550,450],climb_factor,layout=layout),
                    publish('play-top-rest','图标上坐稳休息',[climb[5],climb[5]],[1800,1800],climb_factor,layout=layout),
                    publish('play-climb-down','扶稳后爬下图标',[climb[5],*climb[7:]],[450,550,650,650,550,400],climb_factor,layout=layout)]
        entries[-2]['support_contact'] = [.54,.68]
    paths = [ROOT/'assets/actions/catalog.json', ROOT/'frontend/public/actions/catalog.json']
    # Only replace our own entries, retaining existing source and preview data.
    for path in paths:
        catalog = json.loads(path.read_text(encoding='utf-8'))
        by_id = {a['id']:a for a in catalog}
        additions = entries if path == paths[0] else [dict(a,atlas=a['atlas'][:-4]+'.webp',poster=a['poster'][:-4]+'.webp') for a in entries]
        by_id.update({a['id']:a for a in additions})
        path.write_text(json.dumps(list(by_id.values()),ensure_ascii=False,indent=2),encoding='utf-8')
    previews=[]
    for entry in entries:
        atlas=Image.open(ROOT/'assets'/entry['atlas']).convert('RGBA')
        sheet=Image.new('RGB',atlas.size,'#334252');sheet.paste(atlas,mask=atlas.getchannel('A'))
        sheet.save(WORK/(entry['id']+'-review.jpg'))
        previews.append(sheet)
    print('Published '+', '.join(a['id'] for a in entries))


if __name__ == '__main__':
    main()
