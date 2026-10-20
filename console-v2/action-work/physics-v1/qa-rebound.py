"""Render the actual Qt physics/pose path without opening a desktop window."""
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication
from pet import PetRenderer, PetState

app = QApplication([])
output = root.parent / '.electron-build/rebound-qa'
frames = output / 'frames'
frames.mkdir(parents=True, exist_ok=True)
state, renderer = PetState(), PetRenderer()
state.physics.launch((130, 0), (0, -150))
start = state.started
rows = []
for index in range(240):
    with patch('pet.time.monotonic', return_value=start+index/30):
        if index:
            state.physics.step(1/30, (0, 0, 280, 500))
        sprite = QImage(180, 190, QImage.Format.Format_ARGB32_Premultiplied)
        sprite.fill(0)
        painter = QPainter(sprite)
        renderer.draw(painter, state)
        painter.end()
    image = QImage(440, 730, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor('#edf3fa'))
    painter = QPainter(image)
    painter.setPen(QColor('#395879'))
    pose = state.physics.animation_frame()
    painter.drawText(14, 22, f'{index/30:.2f}s | bounce {state.physics.collision_count} | tempo {state.physics.animation_speed:.2f}x')
    painter.drawText(14, 44, str(pose or 'idle'))
    painter.setPen(QColor('#a5b9d0'))
    painter.drawLine(0, 710, 440, 710)
    painter.drawImage(QRectF(130, 25+state.physics.y, 180, 190), sprite)
    painter.end()
    image.save(str(frames / f'{index:04}.png'))
    rows.append(dict(time=index/30, y=state.physics.y, pose=pose,
                     collision=state.physics.collision_count,
                     flying=state.physics.flying, active=state.physics.active,
                     speed=state.physics.animation_speed))
(output/'timeline.json').write_text(json.dumps(rows, indent=2), encoding='utf-8')
print(str(output))
