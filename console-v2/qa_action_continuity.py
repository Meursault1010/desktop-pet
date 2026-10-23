"""Render before/after through the actual desktop renderer; no live pet touched."""
import json
import os
from pathlib import Path
import statistics
import time
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from pet import PetRenderer, PetState
from action_inbetweens import MAX_PREPARED_PAIRS, _prepared


def main():
    app = QApplication.instance() or QApplication([])
    output = Path(__file__).resolve().parent.parent/'.electron-build/motion-continuity-qa'
    output.mkdir(parents=True,exist_ok=True)
    timings, results = [], []
    for key, seconds in [('sit-neat',3.6),('prone-rest',3.6),('stretch',2.6),('lazy-roll-toward',7.5)]:
        state, renderer = PetState(), PetRenderer()
        state.action_player.play(key,now=100)
        frames = output/key
        frames.mkdir(exist_ok=True)
        for i in range(round(seconds*50)):
            t = 100+i/50
            paired = QImage(400,220,QImage.Format.Format_ARGB32_Premultiplied)
            paired.fill(QColor('#e8eff6'))
            label = QPainter(paired)
            label.setPen(QColor('#315273'))
            label.drawText(18,18,'Original')
            label.drawText(218,18,'Optimized')
            label.end()
            for mode in (0,1):
                sprite = QImage(180,190,QImage.Format.Format_RGBA8888)
                sprite.fill(0)
                start = time.perf_counter()
                with patch('pet.time.monotonic',return_value=t):
                    painter=QPainter(sprite)
                    if mode:
                        renderer.draw_pose(painter,state)
                    else:
                        with patch('pet.sample_pose',return_value=None):
                            renderer.draw_pose(painter,state)
                    painter.end()
                elapsed = (time.perf_counter()-start)*1000
                if mode:
                    timings.append(elapsed)
                compositing = QPainter(paired)
                compositing.drawImage(10+mode*200,22,sprite)
                compositing.end()
            paired.save(str(frames/f'{i:04}.png'))
        results.append({'action':key,'frames':round(seconds*50)})
    result={'clips':results,'render_ms_median':statistics.median(timings),
            'render_ms_p95':sorted(timings)[int(len(timings)*.95)],
            'render_ms_max':max(timings),
            'prepared_pairs':f'{len(_prepared)}/{MAX_PREPARED_PAIRS}'}
    (output/'render-report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
