import json,hashlib
from pathlib import Path
from PIL import Image,ImageDraw
import numpy as np
from build_dance_25d import ROOT,SOURCE,BRIDGES,OUT,clean_cell
folder=ROOT/'assets/actions/music-waltz'
report=json.loads((folder/'choreography.json').read_text())
action=next(a for a in json.loads((ROOT/'assets/actions/catalog.json').read_text(encoding='utf-8')) if a['id']=='music-waltz')
assert report['durations']==action['durations']
track=json.loads((folder/'footwork.json').read_text());pages=json.loads((folder/'pages.json').read_text())
expected=[]
for name in report['order']:
    source=SOURCE/'consistent-keys'/name
    if not source.exists():source=BRIDGES/name
    with Image.open(source) as im:expected.append(clean_cell(np.array(im.convert('RGBA'))))
checks=[]
with Image.open(folder/'atlas.png') as atlas, Image.open(ROOT/'frontend/public/actions/music-waltz/atlas.webp') as web:
    for page in pages['pages']:
        with Image.open(folder/page['file']) as im:
            for index in range(page['first'],page['first']+page['count']):
                x=index%action['columns']*256;y=index//action['columns']*256
                cell=atlas.crop((x,y,x+256,y+256));local=index-page['first'];px=local%pages['columns']*256;py=local//pages['columns']*256
                reference=expected[track['rows'][index]['source_frame']].tobytes()
                assert cell.tobytes()==reference,('source',index)
                assert im.crop((px,py,px+256,py+256)).tobytes()==reference,('page',index)
                assert web.crop((x,y,x+256,y+256)).tobytes()==reference,('web',index)
                assert cell.getchannel('A').getbbox() is not None
                alpha=np.array(cell)[:,:,3]
                assert not any(np.any(edge>16) for edge in (alpha[0],alpha[-1],alpha[:,0],alpha[:,-1])),('clip',index)
                checks.append({'frame':index,'source':report['order'][track['rows'][index]['source_frame']],'sha256':hashlib.sha256(reference).hexdigest(),'source_page_web_equal':True,'clipped':False})
(OUT/'frame-audit.json').write_text(json.dumps({'frames_checked':len(checks),'unique_drawings':len(expected),'optical_flow':False,'morphing':False,'all_passed':True,'checks':checks},indent=2),encoding='utf-8')
# Before/after evidence: old interpolated middle vs the two clean source drawings.
old_report=json.loads((BRIDGES/'build-report.json').read_text());old=Image.open(BRIDGES/'atlas.png')
starts=[];n=0
for t in old_report['transitions']:starts.append(n);n+=t['samples']
ranked=sorted(range(len(starts)),key=lambda i:old_report['transitions'][i]['largest_step'],reverse=True)[:5]
board=Image.new('RGB',(768,5*280),'#cedfee');draw=ImageDraw.Draw(board)
for row,i in enumerate(ranked):
    t=old_report['transitions'][i];index=starts[i]+t['samples']//2
    x=index%old_report['columns']*256;y=index//old_report['columns']*256
    cells=[expected[report['order'].index(t['from'])],old.crop((x,y,x+256,y+256)),expected[report['order'].index(t['to'])]]
    for col,im in enumerate(cells):board.paste(im,(col*256,row*280+24),im)
    for col,label in enumerate(('Clean start','REMOVED: optical-flow middle','Clean next drawing')):draw.text((col*256+4,row*280+4),label,fill='#203b50')
board.save(OUT/'repair-before-after.jpg',quality=95)
print('Audited',len(checks),'frames: source, atlas, pages, lossless web mirror and clipping all passed')
