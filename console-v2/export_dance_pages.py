"""Export bounded-size runtime pages and a lossless browser mirror."""
import json
import math
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parent


def export():
    folder=ROOT/'assets/actions/music-waltz'
    catalog_path=ROOT/'assets/actions/catalog.json'
    catalog=json.loads(catalog_path.read_text(encoding='utf-8'))
    action=next(a for a in catalog if a['id']=='music-waltz')
    atlas=Image.open(folder/'atlas.png').convert('RGBA')
    chunks=folder/'pages';chunks.mkdir(exist_ok=True)
    per_page=100;columns=10;pages=[]
    for first in range(0,action['frames'],per_page):
        count=min(per_page,action['frames']-first)
        page=Image.new('RGBA',(columns*256,math.ceil(count/columns)*256))
        for j in range(count):
            n=first+j;x=n%action['columns']*256;y=n//action['columns']*256
            page.paste(atlas.crop((x,y,x+256,y+256)),(j%columns*256,j//columns*256))
        name=f'{first//per_page:02d}.png';page.save(chunks/name,optimize=False)
        pages.append({'file':'pages/'+name,'first':first,'count':count})
    (folder/'pages.json').write_text(json.dumps({'version':1,'per_page':per_page,'columns':columns,'pages':pages},indent=2),encoding='utf-8')
    expected={Path(p['file']).name for p in pages}
    for obsolete in chunks.glob('*.png'):
        if obsolete.name not in expected:obsolete.unlink()
    web=ROOT/'frontend/public/actions/music-waltz';web.mkdir(exist_ok=True)
    atlas.save(web/'atlas.webp',lossless=True,method=3,exact=True)
    Image.open(folder/'poster.png').save(web/'poster.webp',lossless=True,method=3,exact=True)
    web_catalog_path=ROOT/'frontend/public/actions/catalog.json'
    web_catalog=json.loads(web_catalog_path.read_text(encoding='utf-8'))
    mirrored=dict(action,atlas='actions/music-waltz/atlas.webp',poster='actions/music-waltz/poster.webp')
    web_catalog=[mirrored if a['id']=='music-waltz' else a for a in web_catalog]
    web_catalog_path.write_text(json.dumps(web_catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Exported',len(pages),'runtime pages and browser mirror',flush=True)

if __name__=='__main__':export()
