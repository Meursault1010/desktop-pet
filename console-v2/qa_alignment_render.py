"""Exercise alignment in the real Qt renderer, without a running pet window."""
import json
import os
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from action_inbetweens import _pending, prefetch
from pet import PetRenderer, PetState


def main():
    app = QApplication.instance() or QApplication([])
    output = Path(__file__).resolve().parent.parent / '.electron-build/alignment-qa'
    results = []
    for key in ('wait', 'work', 'yawn'):
        state, renderer = PetState(), PetRenderer()
        state.action_player.play(key, now=100.)
        duration = sum(state.action_player.action['durations']) / 1000
        folder = output / key
        folder.mkdir(parents=True, exist_ok=True)
        for index in range(round(duration * 30)):
            now = 100 + index / 30
            prefetch(state.action_player.upcoming_pairs(now))
            for future in list(_pending.values()):
                if not future.cancelled():
                    future.result()
            canvas = QImage(400, 220, QImage.Format.Format_ARGB32_Premultiplied)
            canvas.fill(QColor('#e8eff6'))
            painter = QPainter(canvas)
            painter.setPen(QColor('#315273'))
            painter.drawText(18, 18, 'Original')
            painter.drawText(218, 18, 'Aligned')
            painter.end()
            for mode in (0, 1):
                painter = QPainter(canvas)
                painter.translate(10 + 200 * mode, 22)
                with patch('pet.time.monotonic', return_value=now):
                    if mode:
                        renderer.draw_pose(painter, state)
                    else:
                        with patch('pet.action_frame_offset', return_value=(0., 0.)):
                            renderer.draw_pose(painter, state)
                painter.end()
            assert canvas.save(str(folder / f'{index:04d}.png'))
        # A missing decoded strip must use only the current pose's anchor.
        with patch('pet.time.monotonic', return_value=100 + duration / 3), \
                patch('pet.sample_pose', return_value=None), \
                patch('pet.action_frame_offset', return_value=(0., 0.)) as offsets:
            painter = QPainter(canvas)
            renderer.draw_pose(painter, state)
            painter.end()
            assert offsets.call_args.args[2] == 0.
        results.append(dict(action=key, frames=round(duration * 30), fallback_anchor='passed'))
    (output / 'report.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
