"""Rebuild local assets in one pass, without any network requests."""
import json
from pathlib import Path
import shutil
import sys
from PIL import Image
import build_action_library as build

if __name__=='__main__':
    # Keep generated records until originals finish; no concurrent writers.
    sys.argv=[sys.argv[0]]
    build.main()
    path=build.ROOT/'assets/actions/catalog.json'
    catalog=json.loads(path.read_text(encoding='utf-8'))
    for item in build.NEW:
        raw=build.ROOT/'action-work'/item[0]/'raw.png'
        if not raw.exists():raise RuntimeError(f'Missing source {item[0]}')
        result=build.generate(item) # Reuses raw.png; never invokes the gateway.
        catalog=[a for a in catalog if a['id']!=result['id']]+[result]
    catalog.sort(key=lambda a:(a['category']=='静态姿势',a['origin']=='generated',a['id']))
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copytree(build.ROOT/'assets/actions',build.ROOT/'frontend/public/actions',dirs_exist_ok=True)
    for a in catalog:
        folder=build.ROOT/'assets/actions'/a['id']
        for i in range(a['frames']):
            im=Image.open(folder/f'{i+1:02d}.png')
            assert im.size==(256,256) and im.mode=='RGBA'
            assert im.getchannel('A').getextrema()[0]==0
        assert len(a['durations'])==a['frames'] and min(a['durations'])>0
    print(f'VALIDATED {len(catalog)} entries; {sum(a["frames"] for a in catalog)} frames',flush=True)
