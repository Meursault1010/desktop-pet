"""Rigid two-layer walk: the approved leg drawings only translate and rock."""
import json
import math
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPixmap

ROOT = Path(__file__).resolve().parent / 'assets/motion-v2/walk-rig'
AMPLITUDE = 16.
BODY_DROP = 4.
LIFT = 15.
SWING_TILT = 3.
STANCE = .5
BOB = 1.
ROLL = 1.5
SHADOW_COLOR = (45, 73, 98)
NEAR_LEG = 1
FAR_LEG = 0
LEG_ORDER = (FAR_LEG, NEAR_LEG)


def _data():
    return json.loads((ROOT / 'rig.json').read_text(encoding='utf-8'))


def _home():
    # Both soles straddle the body's centre line; each keeps its authored
    # depth, so the far sole still sits higher instead of being pulled down.
    return tuple((float(leg['home'][0]), float(leg['home'][1])) for leg in _data())


HOME = _home()


@lru_cache(maxsize=1)
def rig():
    data = _data()
    body = QPixmap(str(ROOT / 'body.png'))
    legs = [QPixmap(str(ROOT / f'leg-{i}.png')) for i in range(2)]
    bodies = {'open': body}
    for expression in ('half', 'closed'):
        bodies[expression] = QPixmap(str(ROOT / f'body-{expression}.png'))
    if any(im.isNull() for im in (*bodies.values(), *legs)):
        raise ValueError('缺少步行动作图层')
    return body, tuple(legs), data, bodies


@lru_cache(maxsize=512)
def contact(leg, angle):
    """Shoe ground contact from the untouched sprite outline."""
    data = rig()[2][leg]
    points, pivot = data['boundary'], data['pivot']
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    rotated = [(pivot[0] + (x - pivot[0]) * c - (y - pivot[1]) * s,
                pivot[1] + (x - pivot[0]) * s + (y - pivot[1]) * c) for x, y in points]
    bottom = max(y for x, y in rotated)
    weights = [math.exp((y - bottom) * 1.5) for x, y in rotated]
    return sum(x * w for (x, y), w in zip(rotated, weights)) / sum(weights), bottom


@lru_cache(maxsize=512)
def _lowest(leg, angle):
    """Lowest sole point of the rigidly tilted sprite, in sprite coordinates."""
    data = rig()[2][leg]
    px, py = data['pivot']
    c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return max(py + (y - py) * c + (x - px) * s for x, y in data['boundary'])


def _poses(clock, stride, vector=(1., 0.), energy=1.):
    """Two rigid leg poses, their soles, and how far each foot is lifted."""
    data = rig()[2]
    energy = max(0., min(1., energy))
    phase = (max(0., clock) / stride) % 1
    support = 1 if phase < .5 else 0
    vx, vy = abs(vector[0]), vector[1]
    travel = stride * 256 / 160
    extent = travel * STANCE / 2
    result = []
    lifts = []
    for leg in range(2):
        # Each foot owns exactly half the cycle: it lifts the frame the other
        # lands, so the walk never rests in a both-feet standing pose. Only the
        # stop transition is allowed to settle into the idle stance. The foot
        # recedes exactly as fast as the body advances, so a planted shoe never
        # skates.
        p = (phase + (0.5 if leg == 0 else 0.)) % 1
        angle = 0.
        if p < STANCE:
            shift = extent - travel * p
            lift = 0.
        else:
            u = (p - STANCE) / (1 - STANCE)
            shift = (-extent + 2 * extent * (3 * u * u - 2 * u * u * u)
                     - travel * (1 - STANCE) * (2 * u * u * u - 3 * u * u + u))
            # Fast unweight: sin^2 kept both shoes within a pixel of the floor
            # for ~100ms after every handoff, which read as a "land and stand"
            # pause. cos^6 is still smooth and zero-velocity at lift-off and
            # touchdown, but leaves the floor about three times sooner.
            lift = 1 - math.cos(math.pi * u) ** 6
            # A short rock from the hip keeps the swing foot from reading as a
            # sliding plank: toe-down after toe-off, toe-up before touchdown,
            # and exactly flat while the foot is planted.
            angle = SWING_TILT * math.sin(2 * math.pi * u) * energy
        shift *= energy
        lift *= energy
        home_x, home_y = HOME[leg]
        target = (home_x + vx * shift,
                  home_y + energy * (-abs(vy) * AMPLITUDE + vy * shift - LIFT * lift))
        # Keep the lowest sole point on its target line even while the swing
        # foot rocks, so the tilt never pushes the shoe through the floor.
        bottom = _lowest(leg, angle) if angle else home_y
        result.append((angle, target[0] - data[leg]['anchor'][0],
                       target[1] - bottom, target))
        lifts.append(lift)
    return result, support, energy * -BOB * (1 - math.cos(phase * 4 * math.pi)), lifts


def sample(clock, stride, vector=(1., 0.), energy=1.):
    """Two rigid leg poses and the soles they place on screen."""
    result, support, bob, _ = _poses(clock, stride, vector, energy)
    return result, support, bob


def paint(painter, target, name, clock, vector=(1., 0.), energy=1., shadows=True,
          eye_frame=1):
    body, legs, data, bodies = rig()
    body = bodies['closed' if eye_frame == 10 else 'half' if eye_frame == 4 else 'open']
    from locomotion import walk_stride
    energy = max(0., min(1., energy))
    samples, _, bob, lifts = _poses(clock, walk_stride(name), vector, energy)
    painter.save()
    painter.translate(target.left(), target.top())
    painter.scale(target.width() / 256, target.height() / 256)
    if name == 'walk-left':
        painter.translate(256, 0)
        painter.scale(-1, 1)
    painter.setRenderHint(painter.RenderHint.Antialiasing, True)
    painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, True)
    if shadows:
        # The shadow marks the planted depth even when the near shoe covers the
        # far one. It stays on the floor and fades as its own foot lifts.
        for leg in LEG_ORDER:
            _, _, _, (tx, ty) = samples[leg]
            lift = lifts[leg]
            width, height, alpha = ((62., 7., 46) if leg == NEAR_LEG
                                    else (46., 5.5, 34))
            width *= 1. - .12 * lift
            height *= 1. - .18 * lift
            # A lifted foot keeps a soft shadow instead of losing it entirely:
            # the floor reference matters most while the shoe is in the air.
            alpha = int(alpha * energy * (1. - .4 * lift))
            if alpha <= 0:
                continue
            ground_y = ty + LIFT * lift
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(*SHADOW_COLOR, alpha))
            painter.drawEllipse(QRectF(tx - width / 2,
                                       ground_y - height - .6,
                                       width, height))
    # Both shoes keep their own authored size and outline at every phase.
    for leg in LEG_ORDER:
        angle, dx, dy, _ = samples[leg]
        px, py = data[leg]['pivot']
        painter.save()
        painter.translate(dx, dy)
        if angle:
            painter.translate(px, py)
            painter.rotate(angle)
            painter.translate(-px, -py)
        painter.drawPixmap(QRectF(0, 0, 256, 256), legs[leg], QRectF(legs[leg].rect()))
        painter.restore()
    # Only the torso counterbalances; the planted leg stays flat and the swing
    # leg rocks at the hip. A wider roll lets the shoulders shift over the
    # planted foot, so the short stance at each footfall reads as a weight
    # transfer, not a rest.
    phase = (max(0., clock) / walk_stride(name)) % 1
    painter.save()
    painter.translate(128, 201)
    painter.rotate(energy * ROLL * math.sin(phase * math.tau))
    painter.translate(-128, -201 + bob + BODY_DROP * energy)
    painter.drawPixmap(QRectF(0, 0, 256, 256), body, QRectF(body.rect()))
    painter.restore()
    painter.restore()
