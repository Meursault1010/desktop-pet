from pathlib import Path
import urllib.request, json, re, concurrent.futures, tempfile
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
import io
BASE='https://styles.refero.design'
CACHE=Path(tempfile.gettempdir())/'yuki-refero-styles-20261020'
CACHE.mkdir(exist_ok=True)
def soup(url):
    return BeautifulSoup(urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=30).read(),'html.parser')
def links(s):
    return [(a.get_text(' ',strip=True),a['href']) for a in s.select('a[href]') if a['href'].startswith('/style/')]
def read(item):
    title,path=item
    dest=CACHE/(path.split('/')[-1]+'.json')
    if dest.exists(): return json.loads(dest.read_text(encoding='utf-8'))
    s=soup(BASE+path); pre=s.find('pre'); md=pre.get_text() if pre else s.get_text(' ',strip=True)
    img=next((i.get('src') for i in s.select('img') if 'Screenshot of' in (i.get('alt') or '')),None)
    row={'name':s.find('h1').get_text(' ',strip=True),'url':BASE+path,'md':md,'image':img,'related':links(s)}
    dest.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
    return row
def compact(r):
    md=r['md']; parts=re.split(r'(?m)^## ',md)
    out=[parts[0][:1600]]
    for key in ['Tokens — Spacing','Components','Layout','Motion',"Do's",'Imagery']:
        for part in parts[1:]:
            if part.startswith(key):out.append(part[:1400]);break
    return '\n'.join(out)[:6300]
def gather():
    initial=links(soup(BASE+'/')); rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(read,initial):rows.append(r)
    names={r['name'].lower() for r in rows}; paths={r['url'].replace(BASE,'') for r in rows}
    queues=[r['related'] for r in rows]; candidates=[]
    for idx in range(20):
        for q in queues:
            if idx>=len(q):continue
            t,p=q[idx]; name=t.split(' ',1)[0].lower()
            if p in paths or any(t.lower().startswith(n+' ') for n in names):continue
            paths.add(p);candidates.append((t,p))
        if len(candidates)>=70:break
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(read,candidates):
            if r['name'].lower() not in names:
                rows.append(r); names.add(r['name'].lower())
            if len(rows)>=54:break
    for i,r in enumerate(rows):r['id']=i+1
    (CACHE/'index.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    print('CACHE',CACHE,'COUNT',len(rows))
    print('\n'.join(str(r['id'])+' '+r['name']+' '+r['url'] for r in rows))
def pictures():
    rows=json.loads((CACHE/'index.json').read_text(encoding='utf-8'))
    def fetch(r):
        f=CACHE/(str(r['id'])+'.jpg')
        if not f.exists():f.write_bytes(urllib.request.urlopen(r['image'],timeout=40).read())
        im=Image.open(f);return r['id'],im.size
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:print(list(ex.map(fetch,rows)))
    f=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',19)
    for start in range(0,len(rows),9):
        board=Image.new('RGB',(1800,1380),'#dce2e9');d=ImageDraw.Draw(board)
        for k,r in enumerate(rows[start:start+9]):
            x=k%3*600;y=k//3*460
            d.text((x+14,y+10),str(r['id']).zfill(2)+'  '+r['name'],font=f,fill='#182436')
            img=Image.open(CACHE/(str(r['id'])+'.jpg')).convert('RGB');w,h=img.size
            top=img.crop((0,0,w,min(h,int(w*.71))))
            top.thumbnail((572,405),Image.Resampling.LANCZOS)
            board.paste(top,(x+14,y+44))
        dest=CACHE/('board-'+str(start//9+1)+'.jpg');board.save(dest,quality=91);print(dest)
if __name__=='__main__':
    import sys
    if 'pictures' in sys.argv:pictures()
    elif 'read' in sys.argv:
        rows=json.loads((CACHE/'index.json').read_text(encoding='utf-8'));a=int(sys.argv[2]);b=int(sys.argv[3])
        for r in rows[a-1:b]:print('\n===',r['id'],r['name'],r['url'],'===\n'+compact(r))
    else:gather()
