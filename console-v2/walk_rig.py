"""Rigid two-layer walk: the approved leg drawings only translate and rock."""
import json
import math
from functools import lru_cache
from pathlib import Path
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPixmap

ROOT = Path(__file__).resolve().parent / 'assets/motion-v2/walk-rig'
AMPLITUDE = 16.
# 裙摆不动，只能把上身整体下压，露出的腿才会变短：裙摆行 212 → 220，可视腿 36 → 28 行。
BODY_LOWER = 8.
BODY_DROP = 0.
LIFT = 9.
FAR_LIFT = .85
# 只给前腿：摆动相整条腿绕髋部前后摆几度，腿才会跟着脚走、不像一根杆子横着
# 平移；两端回 0° 与支撑相无缝衔接，支撑相依然垂直于地面。
NEAR_SWING_LEAN = 5.
_LEAN_PEAK = 4 * math.sqrt(3) / 9   # max of sin(2πu)·sin(πu) at u = acos(1/√3)/π
NEAR_HIP = (157., 200.)
# 前腿抬脚用更圆的 cos^4，离地/落地都没有 cos^6 那么"弹"，读起来是抬起来而
# 不是被弹起来。
NEAR_LIFT_POWER = 4.
SWING_TILT = 1.5
# 支撑相原来整段角度为 0，脚掌像一块贴地的木板。改成脚跟着地时脚尖翘起、
# 中段踩平、蹬离前脚跟翘起；摆动相从蹬离角度连续接回落地角度。
STANCE_ROLL = 2.
ROLL_IN, ROLL_OUT = .12, .88
STANCE = .5
BOB = 1.5
ROLL = 1.2
SWAY = .6
BODY_LAG = .04
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


@lru_cache(maxsize=1)
def parts():
    """袜筒与鞋分两层：袜筒只平移保持竖直，鞋绕脚踝滚转。"""
    socks = tuple(QPixmap(str(ROOT / f'sock-{i}.png')) for i in range(2))
    shoes = tuple(QPixmap(str(ROOT / f'shoe-{i}.png')) for i in range(2))
    if any(im.isNull() for im in (*socks, *shoes)):
        raise ValueError('缺少袜筒/鞋子图层')
    return socks, shoes


def _ease(t):
    return t * t * (3 - 2 * t)


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


def _swing_lean(phase):
    """Near leg tilt in degrees: trails while the foot is behind, leads while it
    is in front. sin(2πu) gives the back-then-front sweep; the extra sin(πu)
    brings the angular velocity to zero at both ends, so lift-off and touchdown
    don't kick the leg into motion. Both are 0 at the ends: stance stays plumb."""
    u = (phase - STANCE) / (1 - STANCE)
    if not 0. < u < 1.:
        return 0.
    return NEAR_SWING_LEAN * math.sin(2 * math.pi * u) * math.sin(math.pi * u) / _LEAN_PEAK


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
        if p < STANCE:
            q = p / STANCE
            # 线性滚转会在踩平/离地的拐角处让角速度瞬间归零（实测 9.9°/s² 的
            # 加速度尖峰），读起来是"咔"地一下到位；改成一阶导也归零的缓动。
            if q < ROLL_IN:
                angle = STANCE_ROLL * (1 - _ease(q / ROLL_IN))
            elif q > ROLL_OUT:
                angle = -STANCE_ROLL * _ease((q - ROLL_OUT) / (1 - ROLL_OUT))
            else:
                angle = 0.
            shift = extent - travel * p
            lift = 0.
        else:
            u = (p - STANCE) / (1 - STANCE)
            s = 3 * u * u - 2 * u * u * u
            shift = (-extent + 2 * extent * s
                     - travel * (1 - STANCE) * (2 * u * u * u - 3 * u * u + u))
            # Fast unweight: sin^2 kept both shoes within a pixel of the floor
            # for ~100ms after every handoff, which read as a "land and stand"
            # pause. cos^6 is still smooth and zero-velocity at lift-off and
            # touchdown, but leaves the floor about three times sooner.
            lift = 1 - math.cos(math.pi * u) ** (NEAR_LIFT_POWER if leg == NEAR_LEG else 6.)
            # 从蹬地的脚尖朝下连续接回落地前的脚尖朝上，中段再挑一点让脚跟领先
            angle = (-STANCE_ROLL + 2 * STANCE_ROLL * s
                     + SWING_TILT * math.sin(math.pi * u))
        angle *= energy
        shift *= energy
        lift *= energy
        if leg == 0:
            lift *= FAR_LIFT
        home_x, home_y = HOME[leg]
        # 两脚的静止位相差 10.5px（近脚偏右、远脚偏左）。各按自己的 home 前后
        # 走，会让"近脚在前"那半步跨距 42、"远脚在前"那半步只有 21，一深一浅。
        # 行走时把前后幅度对称到身体中线（头部与裙摆最低点的轴，不是画布中点），
        # 停下（energy→0）再回到原画静止位。
        center = home_x + (140. - home_x) * energy
        target = (center + vx * shift,
                  home_y + energy * (-abs(vy) * AMPLITUDE + vy * shift - LIFT * lift))
        # Keep the lowest sole point on its target line even while the swing
        # foot rocks, so the tilt never pushes the shoe through the floor.
        bottom = _lowest(leg, angle) if angle else home_y
        # 滚动支点是踝关节，不补偿接触点的话整脚会绕踝横着蹭地面
        roll_x = contact(leg, angle)[0] - contact(leg, 0.)[0] if angle else 0.
        result.append((angle, target[0] - data[leg]['anchor'][0] - roll_x,
                       target[1] - bottom, target))
        lifts.append(lift)
    # 上身比脚晚 0.05 拍到位：摆动、起伏、侧摆都滞后一点，重心才有重量感，
    # 不会像两根杆子每拍准时回零。
    return result, support, energy * -BOB * (1 - math.cos((phase - BODY_LAG) * 4 * math.pi)), lifts


def sample(clock, stride, vector=(1., 0.), energy=1.):
    """Two rigid leg poses and the soles they place on screen."""
    result, support, bob, _ = _poses(clock, stride, vector, energy)
    return result, support, bob


def paint(painter, target, name, clock, vector=(1., 0.), energy=1., shadows=True,
          eye_frame=1):
    body, _, data, bodies = rig()
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
    # 袜筒只平移、永不旋转，腿始终垂直于地面；只有鞋绕脚踝滚转。两层同用一
    # 组 (dx, dy)，所以踝点始终咬合，袜筒多留的几行藏在鞋面后面补缝。
    # 前腿例外：摆动相整条腿绕髋部前后摆，脚在后就往后倾、脚在前就往前倾，
    # 两端回正，所以支撑相仍是竖直的。
    socks, shoes = parts()
    phase = (max(0., clock) / walk_stride(name)) % 1
    lean = _swing_lean(phase)
    for leg in LEG_ORDER:
        angle, dx, dy, _ = samples[leg]
        px, py = data[leg]['pivot']
        painter.save()
        painter.translate(dx, dy)
        if leg == NEAR_LEG and lean:
            hx, hy = NEAR_HIP
            painter.translate(hx, hy)
            painter.rotate(lean)
            painter.translate(-hx, -hy)
        painter.drawPixmap(QRectF(0, 0, 256, 256), socks[leg], QRectF(socks[leg].rect()))
        if angle:
            painter.translate(px, py)
            painter.rotate(angle)
            painter.translate(-px, -py)
        painter.drawPixmap(QRectF(0, 0, 256, 256), shoes[leg], QRectF(shoes[leg].rect()))
        painter.restore()
    # Only the torso counterbalances; the planted leg stays flat and the swing
    # leg rocks at the hip. A wider roll lets the shoulders shift over the
    # planted foot, so the short stance at each footfall reads as a weight
    # transfer, not a rest.
    lag = (phase - BODY_LAG) * math.tau
    painter.save()
    painter.translate(128, 201)
    painter.rotate(energy * ROLL * math.sin(lag))
    painter.translate(-128 + energy * SWAY * math.sin(lag),
                      -201 + bob + BODY_DROP * energy + BODY_LOWER)
    painter.drawPixmap(QRectF(0, 0, 256, 256), body, QRectF(body.rect()))
    painter.restore()
    painter.restore()
