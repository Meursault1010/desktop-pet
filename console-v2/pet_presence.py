"""Reversible starlight arrival/departure, independent of sprite artwork."""
import math
import time


class Presence:
    def __init__(self):
        self.value = 1.
        self.target = True
        self.active = False
        self.started = 0.
        self.origin = 1.
        self.duration = .8

    def begin(self, visible, now=None):
        now = time.monotonic() if now is None else now
        self.update(now)
        self.origin = self.value
        self.target = visible
        self.started = now
        self.duration = max(.08, (.85 if visible else .65)*abs(float(visible)-self.origin))
        self.active = abs(self.value-float(visible)) > .00001

    def update(self, now=None):
        if not self.active:
            return False
        now = time.monotonic() if now is None else now
        t = max(0., min(1., (now-self.started)/self.duration))
        eased = t*t*(3-2*t)
        self.value = self.origin+(float(self.target)-self.origin)*eased
        if t >= 1:
            self.active = False
            return True
        return False

    def reset(self, visible):
        self.active = False
        self.target = visible
        self.value = float(visible)

    def body(self):
        v = self.value
        # Rise/fade rather than shrinking the entire character to a point.
        lift = -9*(1-v)
        settle = math.sin(v*math.pi)*.025 if self.target else 0.
        sy = 1-settle
        return v, lift, 1/sy, sy

    def paint_stars(self, painter):
        from PySide6.QtCore import QPointF, QRectF, Qt
        from PySide6.QtGui import QColor, QPainterPath, QPen
        v = self.value
        envelope = math.sin(math.pi*v)**.8
        if envelope <= .001:
            return
        painter.save()
        painter.setRenderHint(painter.RenderHint.Antialiasing)
        # A small silver-blue halo at the feet; stars remain inside the pet's
        # transparent window and never create an input-catching overlay.
        pen = QPen(QColor(145, 199, 233, round(105*envelope)), .8)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(90-49*envelope, 181-5*envelope, 98*envelope, 10*envelope))
        for i in range(18):
            angle = i*2.399963
            radius = 22+((i*19)%45)
            distance = .4+.6*(1-v)
            x = 90+math.cos(angle)*radius*distance
            y = 101+math.sin(angle)*(radius+18)*distance-18*(1-v)
            twinkle = .65+.35*math.sin(i*1.7+v*math.tau*2)
            size = (1.1+(i%3)*.65)*envelope*twinkle
            color = QColor('#b7def8' if i%3 else '#f4fbff')
            color.setAlphaF(min(1., envelope*(.6+.3*twinkle)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            if i%3:
                painter.drawEllipse(QPointF(x, y), size*.5, size*.5)
            else:
                path = QPainterPath()
                path.moveTo(x, y-size*2)
                for dx, dy in ((.35,-.35),(1,0),(.35,.35),(0,2),(-.35,.35),(-1,0),(-.35,-.35)):
                    path.lineTo(x+dx*size, y+dy*size)
                path.closeSubpath()
                painter.drawPath(path)
        painter.restore()
