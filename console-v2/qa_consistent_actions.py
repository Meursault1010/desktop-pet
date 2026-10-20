"""Offline playback review through the shipping renderer; no live pet touched."""
import json
import os
import random
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication
from action_inbetweens import _pending, prefetch
from pet import PetRenderer, PetState


def main():
    app = QApplication.instance() or QApplication([])
    # Offscreen Qt does not enumerate Windows system fonts automatically.
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
    families = QFontDatabase.applicationFontFamilies(font_id)
    assert families, 'Review labels require an explicitly loaded font'
    output = Path(__file__).resolve().parent.parent / '.electron-build/hair-playback'
    output.mkdir(parents=True, exist_ok=True)
    clips = []
    random.seed(19)
    for key in ('comb', 'wait', 'yawn', 'tea'):
        with patch('pet.time.monotonic', return_value=100.):
            state, renderer = PetState(), PetRenderer()
        state.action_player.play(key, now=100.6)
        seconds = sum(state.action_player.action['durations']) / 1000
        # Initial idle is drawn before starting playback below.
        state.action_player.stop()
        clips.append((key, state, renderer, seconds))
    duration = max(item[3] for item in clips) + 1.6
    for index in range(round(duration * 30)):
        elapsed = index / 30
        now = 100 + elapsed
        canvas = QImage(600, 480, QImage.Format.Format_ARGB32_Premultiplied)
        canvas.fill(QColor('#e8eff6'))
        for position, (key, state, renderer, seconds) in enumerate(clips):
            if index == 18:
                state.action_player.play(key, now=100.6)
            prefetch(state.action_player.upcoming_pairs(now))
            for future in list(_pending.values()):
                if not future.cancelled():
                    future.result()
            painter = QPainter(canvas)
            painter.setFont(QFont(families[0], 10))
            x, y = (position % 2) * 300, (position // 2) * 240
            painter.setPen(QColor('#315273'))
            phase = 'idle' if elapsed < .6 or elapsed >= .6 + seconds else 'action'
            painter.drawText(x+16, y+22, f'{key} / {phase}')
            painter.translate(x+60, y+35)
            with patch('pet.time.monotonic', return_value=now):
                renderer.draw(painter, state)
            painter.end()
        assert canvas.save(str(output / f'{index:04d}.png'))
    report = {'fps': 30, 'frames': round(duration * 30),
              'clips': [{'action': key, 'seconds': seconds} for key, _, _, seconds in clips],
              'renderer': 'PetRenderer.draw', 'preloaded': True}
    (output/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
