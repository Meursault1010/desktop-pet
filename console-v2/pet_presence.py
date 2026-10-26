"""Opaque, reversible edge travel sharing the approved ordinary walk model."""
import time
from pathlib import Path
from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap, QTransform

ASSETS = Path(__file__).resolve().parent / 'assets/presence'
ENTER = tuple(f'enter-{i:02d}.png' for i in range(1,11))
EXIT = tuple(f'exit-{i:02d}.png' for i in range(1,8))
ENTER_DURATIONS = (.28,.25,.22,.28,.18,.16,.16,.16,.18,.22)
EXIT_DURATIONS = (.16,.25,.16,.16,.20,.40,.20)


def ease(t):
    t = min(1., max(0., t))
    return t*t*(3-2*t)


class Presence:
    def __init__(self):
        self.value = 1.
        self.target = True
        self.active = False
        self.started = 0.
        self.origin = self.destination = self.home = (0.,0.)
        self.sequence = ()
        self.durations = ()
        self.duration = 0.
        self.frames = {}
        self.edge = 'right'
        self.area = (0,0,1920,1080)
        self.playhead = 0.
        self.direction = 1
        self.entering = True

    def clock(self, now=None):
        now = time.monotonic() if now is None else now
        return min(self.total, max(0., self.playhead + self.direction*(now-self.started)))

    def begin(self, visible, now=None, position=None, area=None, size=None):
        now = time.monotonic() if now is None else now
        if self.active:
            # Reverse the same trajectory and the same pose samples, without a jump.
            cursor = self.clock(now)
            self.direction = 1 if bool(visible) == self.entering else -1
            self.playhead, self.started, self.target = cursor, now, bool(visible)
            self.duration = self.total-cursor if self.direction > 0 else cursor
            return
        x,y = position or (0.,0.)
        width,height = size or (180,190)
        self.area = area or (0,0,1920,1080)
        left,top,aw,ah = self.area
        right = left+aw
        self.home = (x,y)
        self.edge = 'left' if abs(x-left) < abs(right-width-x) else 'right'
        off = (left-width if self.edge == 'left' else right, y)
        # The approved short-limbed model has a narrower silhouette. Expose
        # enough canvas for the actual head, rather than only empty padding.
        peek = (left-width*.38 if self.edge == 'left' else right-width*.62, y)
        self.origin,self.destination = (off,self.home) if visible else (self.home,off)
        self.peek = peek
        self.entering = self.target = bool(visible)
        self.sequence = ENTER + ('idle.png',) if visible else ('idle.png',) + EXIT
        durations = list(ENTER_DURATIONS if visible else EXIT_DURATIONS)
        # Allow enough travel time on wide desktops, retaining observation holds.
        from locomotion import walking_speed
        travel = max(.6, abs(x-peek[0])/walking_speed(48))
        if visible:
            durations[5:8] = [travel/3]*3
            self.walk_start = sum(durations[:5])
            self.walk_end = sum(durations[:8])
        else:
            durations[2:5] = [travel/3]*3
            self.walk_start = sum(durations[:2])
            self.walk_end = sum(durations[:5])
        durations = durations + [.08] if visible else [.16] + durations
        if not visible:
            self.walk_start += .16
            self.walk_end += .16
        self.durations = tuple(durations)
        self.total = self.duration = sum(durations)
        self.playhead,self.direction,self.started = 0.,1,now
        self.value = float(not visible)
        self.active = True
        # Disk IO occurs once at transition setup, never optical flow on the UI thread.
        for i,key in enumerate(self.sequence):
            if key not in self.frames:
                self.frames[key] = QPixmap(str(ASSETS/key))
        # Non-idle presence no longer loads the old optical-flow sheets.

    def motion_key(self, key):
        if key in ('enter-10.png','idle.png'):
            suffix = '-left-bridge.png' if self.edge == 'left' else '-bridge.png'
            return key.replace('.png',suffix)
        return key.replace('.png','-motion.png')

    def update(self, now=None):
        if not self.active:
            return False
        t = self.clock(now)
        done = t >= self.total-1e-8 if self.direction > 0 else t <= 1e-8
        self.value = t/self.total if self.entering else 1-t/self.total
        if done:
            self.value = float(self.target)
            self.active = False
        return done

    def position(self, now=None):
        t = self.clock(now)
        def blend(a,b,p):
            return tuple(x+(y-x)*p for x,y in zip(a,b))
        if self.entering:
            if t < .22:
                return blend(self.origin,self.peek,ease(t/.22))
            return blend(self.peek,self.destination,ease((t-self.walk_start)/(self.walk_end-self.walk_start)))
        if t < self.walk_end:
            return blend(self.origin,self.peek,ease((t-self.walk_start)/(self.walk_end-self.walk_start)))
        withdrawal = self.total-self.durations[-1]
        return blend(self.peek,self.destination,ease((t-withdrawal)/self.durations[-1]))

    def frame(self, now=None):
        if not self.sequence:
            return None
        elapsed = self.clock(now)
        if self.walk_start <= elapsed < self.walk_end:
            from locomotion import frames, walk_stride
            keys = frames('walk-left' if self.entering else 'walk-right')
            # The same step geometry as normal walking, sampled by travel.
            x, _ = self.position(now)
            start = self.peek if self.entering else self.origin
            distance = abs(x-start[0])
            phase = distance / max(1., walk_stride('walk-right'))
            return keys[int(phase*len(keys)) % len(keys)]
        for i,d in enumerate(self.durations):
            if elapsed < d or i == len(self.sequence)-1:
                key = self.sequence[i]
                frame = self.frames.get(key)
                if key != 'idle.png' and self.entering and frame is not None:
                    frame = frame.transformed(QTransform().scale(-1,1))
                if key == 'idle.png' and self.edge == 'left' and frame is not None:
                    frame = frame.transformed(QTransform().scale(-1,1))
                return frame
            elapsed -= d

    def paint(self, painter, now=None):
        frame = self.frame(now)
        if frame is None or frame.isNull():
            return False
        painter.save()
        device = painter.device()
        sx,sy = device.width()/180,device.height()/190
        # Clip to this monitor even if another monitor lies beyond its edge.
        x,y = self.position(now)
        left,top,w,h = self.area
        painter.setClipRect(QRectF(left-x,top-y,w,h))
        painter.scale(sx,sy)
        walking = self.walk_start <= self.clock(now) < self.walk_end
        if self.edge == 'left' and not walking:
            painter.translate(180,0)
            painter.scale(-1,1)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform,True)
        if walking:
            from walk_rig import paint as paint_walk
            start=self.peek if self.entering else self.origin
            end=self.destination if self.entering else self.peek
            sign=1 if end[0]>=start[0] else -1
            paint_walk(painter,QRectF(10,181.875-160*249/256,160,160),
                       'walk-right' if sign>0 else 'walk-left',abs(x-start[0])/max(.01,sx),(sign,0.))
        else:
            painter.drawPixmap(QRectF(0,10,180,180),frame,QRectF(frame.rect()))
        painter.restore()
        return True

    def reset(self, visible):
        self.active = False
        self.target = bool(visible)
        self.value = float(visible)
        self.sequence = ()
