"""Build the approved screen revision; no generation or original art mutation."""
import json
import shutil
from datetime import datetime
from PIL import Image
from build_action_library import ROOT,export

def install():
    source=ROOT/'action-work/screen-v2'
    backup=ROOT/('backup-screen-assets-'+datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir()
    shutil.copytree(ROOT/'assets/actions/screen',backup/'screen')
    shutil.copy2(ROOT/'assets/actions/catalog.json',backup/'catalog.json')
    paths=sorted((source/'透明静帧').glob('frame_*.png'))
    assert len(paths)==12
    record=export('screen','口袋电子屏幕','日常',[Image.open(p) for p in paths],'generated',[str(p) for p in paths])
    record.update(durations=[350,180,180,240,250,550,180,180,200,300,180,700],loop_start=5,review='修订版 · 取出一次，持续持屏操作',revision=2)
    path=ROOT/'assets/actions/catalog.json'
    catalog=json.loads(path.read_text(encoding='utf-8'))
    catalog=[record if a['id']=='screen' else a for a in catalog]
    assert len(catalog)==31
    path.write_text(json.dumps(catalog,ensure_ascii=False,indent=2),encoding='utf-8')
    shutil.copytree(ROOT/'assets/actions',ROOT/'frontend/public/actions',dirs_exist_ok=True)
    shutil.copy2(ROOT/'assets/actions/screen/06.png',ROOT/'assets/actions/screen/poster.png')
    shutil.copy2(ROOT/'assets/actions/screen/poster.png',ROOT/'frontend/public/actions/screen/poster.png')
    # Export actual scheduled preview, not the generic export() default timing.
    images=[]
    for i in range(12):
        frame=Image.open(ROOT/f'assets/actions/screen/{i+1:02d}.png')
        bg=Image.new('RGB',(256,256),'#303b4c');bg.paste(frame,mask=frame.getchannel('A'));images.append(bg)
    images[0].save(ROOT/'qa/actions/screen.gif',save_all=True,append_images=images[1:],duration=record['durations'],loop=0)
    images[5].save(ROOT/'qa/actions/screen-operating.gif',save_all=True,append_images=images[6:],duration=record['durations'][5:],loop=0)
    print('Installed screen revision 2: 12 frames; loop starts at frame 6. Backup:',backup)

if __name__=='__main__':install()
