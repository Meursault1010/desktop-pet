"""Offscreen QA for the integrated vertical walk rig."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

from locomotion import walk_stride
from pet import DesktopPet
from settings_model import Preferences

ROOT = Path(__file__).resolve().parent / 'qa/vertical-runtime'
FONT = 'C:/Windows/Fonts/msyh.ttc'


def render(pet, name, phase):
    state = pet.state
    now = time.monotonic()
    state.action_player.stop()
    state.sleep.phase = 'awake'
    state.physics.cancel()
    state.gait_name = name
    state.gait_clock = phase * walk_stride(name)
    state.gait_until = now + 10
    state.gait_energy = 1.
    state.gait_energy_at = now
    state.gait_vector = (0., -1.) if name == 'walk-up' else (0., 1.)
    state.direction = 1
    image = QImage(360, 380, QImage.Format.Format_RGBA32FPx4_Premultiplied)
    image.setDevicePixelRatio(2.)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    pet.renderer.draw_pose(painter, state)
    painter.end()
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombytes('RGBA', (rgba.width(), rgba.height()),
                           bytes(rgba.constBits()))


def main():
    app = QApplication([])
    pet = DesktopPet(Preferences(random_movement=False, auto_snap=False))
    pet.animator.timer.stop()
    ROOT.mkdir(parents=True, exist_ok=True)
    frames = {}
    for name in ('walk-up', 'walk-down'):
        rows = []
        for step in range(8):
            phase = step / 8
            image = render(pet, name, phase)
            image.save(ROOT / f'{name}-{step}.png')
            canvas = Image.new('RGBA', image.size, (29, 43, 56, 255))
            canvas.alpha_composite(image)
            rows.append(canvas.convert('RGB'))
        frames[name] = rows
    cell = frames['walk-up'][0].size
    header = 24
    sheet = Image.new('RGB', (cell[0] * 4, 2 * (2 * cell[1] + header)), '#263747')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype(FONT, 16)
    for section, name in enumerate(('walk-up', 'walk-down')):
        base = section * (2 * cell[1] + header)
        draw.text((8, base + 4), name, font=font, fill='#dfe8f2')
        for half in range(2):
            for column in range(4):
                index = half * 4 + column
                sheet.paste(frames[name][index],
                            (column * cell[0], base + header + half * cell[1]))
                draw.text((column * cell[0] + 8, base + header + half * cell[1] + 6),
                          f'{index}/8', font=font, fill='#9fb3c8')
    sheet.save(ROOT / 'contact.png')
    print(ROOT / 'contact.png')
    pet.hide()
    pet.deleteLater()


if __name__ == '__main__':
    main()
