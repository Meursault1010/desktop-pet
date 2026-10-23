"""Offscreen sharpness check for the click reaction at source-draw level."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import action_inbetweens as ai  # noqa: E402
from click_reaction import ClickReaction  # noqa: E402
from pet import DesktopPet  # noqa: E402
from settings_model import Preferences  # noqa: E402

OUT = Path(__file__).resolve().parent / 'after-fix'
OUT.mkdir(exist_ok=True)
FIXED = 1000.0
TIMES = (.02, .05, .08, .12, .16, .20, .35, .60, .90, 1.20, 1.50)


def sharpness(image):
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    width, height = rgba.width(), rgba.height()
    raw = np.frombuffer(rgba.bits(), np.uint8).reshape(height, rgba.bytesPerLine())
    pixels = raw[:, :width * 4].reshape(height, width, 4).astype(np.float32)
    gray = pixels[..., :3] @ np.array([.299, .587, .114], np.float32)
    alpha = pixels[..., 3]
    lap = (4 * gray[1:-1, 1:-1] - gray[:-2, 1:-1] - gray[2:, 1:-1]
           - gray[1:-1, :-2] - gray[1:-1, 2:])
    return float(np.abs(lap[alpha[1:-1, 1:-1] > 127]).mean())


def render(pet):
    image = QImage(180, 190, QImage.Format.Format_RGBA32FPx4_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    pet.renderer.draw(painter, pet.state)
    painter.end()
    return image


def old_compose(source, reaction, now):
    displayed = QImage(source.size(), source.format())
    displayed.fill(0)
    painter = QPainter(displayed)
    dx, dy, angle, sx, sy, shear = reaction.transform(now)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
    painter.translate(90 + dx, 178 + dy)
    painter.rotate(angle)
    painter.shear(shear, 0)
    painter.scale(sx, sy)
    painter.translate(-90, -178)
    painter.drawImage(0, 0, source)
    painter.end()
    return displayed


def save(image, name):
    image.scaled(image.width() * 3, image.height() * 3,
                 Qt.AspectRatioMode.IgnoreAspectRatio,
                 Qt.TransformationMode.SmoothTransformation).save(str(OUT / name))


def prepare_transition(pet, now):
    before, after, progress = pet.state.action_player.motion_sample(now)
    key = ai.pair_key(before, after)
    if progress > 0 and key in ai.manifest():
        ai.frames(ai.manifest()[key])


def sequence(click):
    with patch('time.monotonic', return_value=FIXED):
        pet = DesktopPet(Preferences())
        pet.animator.timer.stop()
        pet.state.click_reaction.clear()
        pet.state.action_player.play('shy')
        pet.state.action_player.started = FIXED
        if click:
            pet.state.click_reaction.trigger('shy', 125, now=FIXED)
    samples = []
    legacy = ClickReaction()
    legacy.trigger('shy', 125, now=FIXED)
    for moment in TIMES:
        with patch('time.monotonic', return_value=FIXED + moment):
            prepare_transition(pet, FIXED + moment)
            image = render(pet)
            old = (None if click else sharpness(old_compose(image.copy(), legacy,
                                                            FIXED + moment)))
            save(image, f"{'51-click' if click else '50-base'}-{moment:.2f}-3x.png")
        samples.append((moment, sharpness(image), old))
    pet.close()
    pet.deleteLater()
    return samples


def main():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    base = sequence(False)
    clicked = sequence(True)
    print(f'{"t":>5} {"no-click":>9} {"click":>8} {"ratio":>7} {"old":>8} {"old-ratio":>10}')
    for (moment, base_lap, old_lap), (_, click_lap, _) in zip(base, clicked):
        print(f'{moment:5.2f} {base_lap:9.2f} {click_lap:8.2f}'
              f' {click_lap / base_lap:7.3f} {old_lap:8.2f} {old_lap / base_lap:10.3f}')


if __name__ == '__main__':
    main()
