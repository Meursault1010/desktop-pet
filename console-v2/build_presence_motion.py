"""Build local single-source optical-flow inbetweens for presence poses."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image
from build_action_inbetweens import interpolate

ROOT = Path(__file__).resolve().parent / 'assets/presence'

def main():
    cv2.setNumThreads(1)
    report = {}
    # Reuse the shipping standing pose for a precise handoff to the idle renderer.
    import os
    os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
    from PySide6.QtWidgets import QApplication
    from pet import PetRenderer
    app = QApplication.instance() or QApplication([])
    renderer = PetRenderer()
    image = renderer.motion_image(0,1).toImage()
    image.save(str(ROOT/'idle-source.png'))
    idle = Image.new('RGBA',(384,384))
    pose = Image.open(ROOT/'idle-source.png').convert('RGBA').resize((341,341),Image.Resampling.LANCZOS)
    idle.paste(pose,(21,32))
    idle.save(ROOT/'idle.png')
    for kind, count in [('enter', 10), ('exit', 7)]:
        for i in range(1, count):
            a, b = [np.array(Image.open(ROOT/f'{kind}-{n:02d}.png').convert('RGBA').resize((256,256), Image.Resampling.LANCZOS)) for n in (i,i+1)]
            frames, review = interpolate(a,b)
            sheet = Image.new('RGBA', (256*5,256*5))
            for j, frame in enumerate(frames):
                sheet.paste(Image.fromarray(frame), ((j%5)*256,(j//5)*256))
            sheet.save(ROOT/f'{kind}-{i:02d}-motion.png')
            report[f'{kind}-{i:02d}'] = review
            print(kind,i,review,flush=True)
    for before, after in [('enter-10','idle'),('idle','exit-01')]:
        a,b = [np.array(Image.open(ROOT/f'{name}.png').convert('RGBA').resize((256,256),Image.Resampling.LANCZOS)) for name in (before,after)]
        frames,review = interpolate(a,b)
        sheet = Image.new('RGBA',(1280,1280))
        for j,frame in enumerate(frames):
            sheet.paste(Image.fromarray(frame),((j%5)*256,(j//5)*256))
        sheet.save(ROOT/f'{before}-bridge.png')
        report[f'{before}-bridge'] = review
    for before,after in [('enter-10','idle'),('idle','exit-01')]:
        images = [Image.open(ROOT/f'{name}.png').convert('RGBA').resize((256,256),Image.Resampling.LANCZOS) for name in (before,after)]
        index = 1 if after == 'idle' else 0
        images[index] = images[index].transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        frames,review = interpolate(*[np.array(im) for im in images])
        sheet = Image.new('RGBA',(1280,1280))
        for j,frame in enumerate(frames):
            sheet.paste(Image.fromarray(frame),((j%5)*256,(j//5)*256))
        sheet.save(ROOT/f'{before}-left-bridge.png')
        report[f'{before}-left-bridge'] = review
    (ROOT/'motion-report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')

if __name__ == '__main__':
    main()
