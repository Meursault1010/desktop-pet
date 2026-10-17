"""Record completed static QA and synchronize the reviewed catalog."""
import json
import shutil
from build_action_library import ROOT, NEW

path=ROOT/'assets/actions/catalog.json'
catalog=json.loads(path.read_text(encoding='utf-8'))
for a in catalog:
    if a['origin']=='generated' and (ROOT/'action-work'/a['id']/'reviewed.txt').exists():
        a['review']='首轮静帧检查通过 · 六关键帧'
assert len(catalog)==31
assert all(any(a['id']==item[0] for a in catalog) for item in NEW)
path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copytree(ROOT/'assets/actions',ROOT/'frontend/public/actions',dirs_exist_ok=True)
print('31 catalog entries synchronized; 28 animated sequences and 3 static poses.')
