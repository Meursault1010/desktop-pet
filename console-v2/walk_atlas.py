"""Baked eight-frame horizontal walk: one whole-body image per step pose."""
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap

ROOT = Path(__file__).resolve().parent / 'assets/motion-v2/walk-atlas'
FRAMES = 8
CELL = 256
BASELINE = 249


@lru_cache(maxsize=1)
def frames():
    result = tuple(QPixmap(str(ROOT / f'{i:02d}.png')) for i in range(FRAMES))
    if any(p.isNull() or p.width() != CELL or p.height() != CELL for p in result):
        raise ValueError('缺少整帧步行动作素材')
    return result


@lru_cache(maxsize=2)
def _directional(name):
    if name != 'walk-left':
        return frames()
    result = tuple(
        QPixmap(str(ROOT / 'left' / f'{i:02d}.png')) for i in range(FRAMES)
    )
    if any(p.isNull() or p.width() != CELL or p.height() != CELL for p in result):
        raise ValueError('缺少向左步行动作素材')
    return result


def prewarm():
    frames()
    _directional('walk-left')


def frame_index(clock, name):
    from locomotion import walk_stride
    phase = (max(0., clock) / walk_stride(name)) % 1.0
    return min(FRAMES - 1, int(phase * FRAMES))


def paint(painter, target, name, clock, vector=(1., 0.), energy=1., shadows=True,
          eye_frame=1):
    pixmap = _directional(name)[frame_index(clock, name)]
    painter.save()
    painter.translate(target.left(), target.top())
    painter.scale(target.width() / CELL, target.height() / CELL)
    painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, True)
    painter.drawPixmap(QRectF(0, 0, CELL, CELL), pixmap, QRectF(pixmap.rect()))
    painter.restore()
