"""Continuous front/back walk used while travelling mostly up or down."""
import json
import math
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPixmap

ROOT = Path(__file__).resolve().parent / 'assets/motion-v2/walk-vertical'
GROUND = 181.875
SHADOW_COLOR = (45, 73, 98)
NAMES = ('walk-up', 'walk-down')
# Longest local fore/aft travel of a foot inside the 256px canvas. The stance
# foot slides back by this much while the window moves forward, which keeps a
# visible step under the planted leg instead of a pure window translation.
FOOT_TRAVEL = 4.0


@lru_cache(maxsize=1)
def rig():
    data = json.loads((ROOT / 'rig.json').read_text(encoding='utf-8'))
    bodies = {name: QPixmap(str(ROOT / data[name]['body']))
              for name in ('up', 'down')}
    legs = {name: tuple(QPixmap(str(ROOT / file))
                        for file in data[name]['legs'])
            for name in ('up', 'down')}
    if any(im.isNull() for im in (*bodies.values(), *legs['up'], *legs['down'])):
        raise ValueError('缺少纵向走路图层')
    return data, bodies, legs


def direction(name):
    return name.rsplit('-', 1)[-1]


def frame_rect(name):
    data, bodies, _ = rig()
    baseline = data[direction(name)]['baseline'] / bodies[direction(name)].width()
    return QRectF(10, GROUND - 160 * baseline, 160, 160)


def _poses(phase, data, energy, travel=1.):
    energy = max(0., min(1., energy))
    phase %= 1.
    moves = []
    planted = []
    for index in range(2):
        p = (phase + (0. if index == 0 else .5)) % 1.
        if p < .5:
            # The supporting foot travels from front to back while the window
            # advances, so it never skates forward with the whole sprite.
            aft = travel * FOOT_TRAVEL * (p / .5 * 2. - 1.) * energy
            moves.append((0., 0., aft, 0.))
            planted.append(1.)
            continue
        u = (p - .5) / .5
        lift = 1 - math.cos(math.pi * u) ** 6
        side = -1. if index == 0 else 1.
        wave = math.sin(math.pi * u)
        aft = travel * FOOT_TRAVEL * (1. - 2. * u) * energy
        # Qt's positive rotation is clockwise, which swings a foot below the
        # pivot to the left; the left leg needs the positive outward rock.
        moves.append((-side * data['tilt'] * wave * energy,
                      side * data['outward'] * wave * wave * energy,
                      aft - data['lift'] * lift * energy, lift * energy))
        planted.append(1. - lift)
    # The torso follows the centre of gravity: while one foot carries the
    # body, shift and roll over that foot. At each handoff both feet carry
    # equal weight, so this passes through the neutral stance smoothly.
    total = sum(planted)
    weight_shift = ((planted[1] - planted[0]) / total) if total else 0.
    bob = energy * (data['body_drop'] - data['bob'] * (1 - math.cos(4 * math.pi * phase)))
    sway = energy * data['sway'] * weight_shift
    roll = energy * data['roll'] * weight_shift
    return moves, bob, sway, roll


def sample(name, clock, energy=1.):
    """Limb transforms, body offset and soles for tests and QA."""
    key = direction(name)
    data = rig()[0][key]
    phase = (max(0., clock) / data['stride']) % 1.
    travel = 1. if key == 'up' else -1.
    moves, bob, sway, roll = _poses(phase, data, energy, travel)
    soles = [(data['feet'][index] + move[1],
              data['baseline'] + move[2]) for index, move in enumerate(moves)]
    return moves, bob, sway, roll, soles


def paint(painter, target, name, clock, energy=1., shadows=True):
    data, bodies, legs = rig()
    key = direction(name)
    spec = data[key]
    phase = (max(0., clock) / spec['stride']) % 1.
    moves, bob, sway, roll = _poses(phase, spec, energy, 1. if key == 'up' else -1.)
    body = bodies[key]
    canvas = body.width()
    painter.save()
    painter.translate(target.left(), target.top())
    painter.scale(target.width() / canvas, target.height() / canvas)
    painter.setRenderHint(painter.RenderHint.Antialiasing, True)
    painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, True)
    if shadows:
        for index, (_, dx, dy, lift) in enumerate(moves):
            width = 28. - 5. * lift
            height = 4.3 - .7 * lift
            alpha = int((27 if index == 0 else 24) * (1. - .45 * lift))
            if alpha <= 0:
                continue
            cx = spec['feet'][index] + dx * .75
            # Contact follows the foot's fore/aft depth, not its lift.
            cy = spec['baseline'] + dy + spec['lift'] * lift * energy
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(*SHADOW_COLOR, alpha))
            painter.drawEllipse(QRectF(cx - width / 2, cy - height - 1.2,
                                       width, height))
    for index, (angle, dx, dy, _) in enumerate(moves):
        px, py = spec['pivots'][index]
        painter.save()
        painter.translate(dx, dy)
        if angle:
            painter.translate(px, py)
            painter.rotate(angle)
            painter.translate(-px, -py)
        painter.drawPixmap(QRectF(0, 0, canvas, canvas), legs[key][index],
                           QRectF(legs[key][index].rect()))
        painter.restore()
    painter.save()
    painter.translate(sway, bob)
    painter.translate(128, 205)
    painter.rotate(roll)
    painter.translate(-128, -205)
    painter.drawPixmap(QRectF(0, 0, canvas, canvas), body, QRectF(body.rect()))
    painter.restore()
    painter.restore()
