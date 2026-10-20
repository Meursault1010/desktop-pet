"""Render actual window coordinates and pose phases without touching live pets."""
import json
import os
from pathlib import Path
import random
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from action_inbetweens import prefetch, _pending
from pet import DesktopPet
from settings_model import Preferences


def main():
    app = QApplication.instance() or QApplication([])
    output = Path(os.environ.get('YUKI_ROLL_QA_OUTPUT',
                    Path(__file__).resolve().parent.parent/'.electron-build/roll-motion-qa'))
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for key in ('lazy-roll-toward', 'lazy-roll-away'):
        pet = DesktopPet(Preferences())
        pet.show()
        pet.animator.timer.stop()
        pet.move(360, 240)
        player = pet.state.action_player
        random.seed(8)
        player.play(key, now=100)
        total = sum(player.action['durations'])/1000
        frames = output/key
        frames.mkdir(exist_ok=True)
        positions = []
        for i in range(round(total*25)+1):
            now = 100+min(total-1e-5, i/25)
            prefetch(player.upcoming_pairs(now))
            # QA only: warm the worker before measuring/rendering, never do
            # this blocking wait in the real paint/input path.
            for future in list(_pending.values()):
                if not future.cancelled():
                    future.result()
            pet.animator.advance_roll(now)
            positions.append(pet.y())
            canvas = QImage(680, 450, QImage.Format.Format_ARGB32_Premultiplied)
            canvas.fill(QColor('#e8eff6'))
            painter = QPainter(canvas)
            painter.setPen(QColor('#bccbd9'))
            painter.drawLine(0, 220, 680, 220)
            painter.save()
            painter.translate(pet.x(), 40+pet.y()-240)
            with patch('pet.time.monotonic', return_value=now):
                pet.renderer.draw_pose(painter, pet.state)
            painter.restore()
            painter.end()
            canvas.save(str(frames/f'{i:04}.png'))
        direction = -1 if key == 'lazy-roll-toward' else 1
        assert (positions[-1]-positions[0])*direction > 50
        assert all((b-a)*direction >= 0 for a, b in zip(positions, positions[1:]))
        reports.append(dict(action=key, frames=len(positions), duration_s=total,
                            start_y=positions[0], end_y=positions[-1],
                            displacement_px=positions[-1]-positions[0]))
        pet.close()
        pet.deleteLater()
        app.processEvents()
    (output/'report.json').write_text(json.dumps(reports, indent=2), encoding='utf-8')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    main()
