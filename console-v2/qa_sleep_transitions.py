"""Render the real sleep painter and record animation continuity evidence."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import json
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image, ImageDraw
from PySide6.QtGui import QColor, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

from pet import PetRenderer, PetState
from pet_sleep import ASSETS, MANIFEST, SETTLE_SECONDS

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT.parent/'docs/验收资料/sleep-transitions-20261020'


def pillow_array(image):
    raw = np.array(image).astype('float32')
    raw[:, :, :3] *= raw[:, :, 3:4]/255
    return raw


def main():
    app=QApplication.instance() or QApplication([])
    QFontDatabase.addApplicationFont('C:/Windows/Fonts/comicbd.ttf')
    state, renderer=PetState(),PetRenderer()
    cycle=state.sleep
    cycle.phase,cycle.started='settling',100.
    pet=NS(state=state,renderer=renderer,state_changed=Mock())
    OUTPUT.mkdir(parents=True,exist_ok=True)
    previews=[]
    for i in range(210):
        elapsed=i/30
        now=100+elapsed
        if cycle.phase=='settling' and elapsed>=SETTLE_SECONDS:
            cycle.phase='asleep';cycle.breath_started=100+SETTLE_SECONDS
        if cycle.phase=='asleep' and elapsed>=5.4:
            cycle.wake(pet,'预览唤醒',now)
        canvas=QImage(400,450,QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(QColor('#eff4fc'))
        p=QPainter(canvas)
        p.setPen(QColor('#384d74'))
        label={'settling':'SETTLING / slow eye closure','asleep':'DEEP SLEEP / breathing','waking':'WAKING / gentle head lift'}[cycle.phase]
        p.drawText(20,28,label)
        p.translate(20,45);p.scale(2,2)
        with patch('pet.time.monotonic',return_value=now):renderer.draw(p,state)
        p.end()
        image=canvas.convertToFormat(QImage.Format.Format_RGBA8888)
        im=Image.frombytes('RGBA',(image.width(),image.height()),bytes(image.bits()),'raw','RGBA',image.bytesPerLine())
        previews.append(im.convert('RGB'))
        if i in (0,35,48,135,170,190,209):im.save(OUTPUT/f'qt-{i:03}.png')
    previews[0].save(OUTPUT/'sleep-wake-playback.gif',save_all=True,
                    append_images=previews[1:],duration=33,loop=0,disposal=2)
    report={'fps':MANIFEST['fps'],'settle':MANIFEST['settle'],'wake':MANIFEST['wake'],
            'rendered_preview_frames':len(previews),'sequences':{}}
    for name in ('settle','wake'):
        frames=[pillow_array(Image.open(ASSETS/'transitions'/f'{name}-{i:03}.png'))
                for i in range(MANIFEST[name]['count'])]
        step=[float(np.abs(a-b).mean()) for a,b in zip(frames,frames[1:])]
        pillow=[bool(np.array_equal(a[190:225,274:293],frames[0][190:225,274:293])) for a in frames]
        report['sequences'][name]={'max_whole_canvas_step_0_255':round(max(step),6),
                                  'mean_whole_canvas_step_0_255':round(float(np.mean(step)),6),
                                  'interior_pillow_unchanged':all(pillow)}
    (OUTPUT/'animation-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
