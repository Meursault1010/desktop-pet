"""Damped, volume-preserving jelly feedback in the logical pet canvas."""
import math
import time


class ClickReaction:
    def __init__(self):
        self.clear()

    def clear(self):
        self.started = None
        self.kind = 'press'
        self.direction = 0.

    def trigger(self, kind, x, now=None):
        # Restart rather than accumulate impulses: rapid clicks cannot deform
        # the character or fling it outside its transparent window.
        self.started = time.monotonic() if now is None else now
        self.kind = kind
        self.direction = max(-1., min(1., (x-90)/55))

    def transform(self, now=None):
        if self.started is None:
            return 0., 0., 0., 1., 1., 0.
        elapsed = max(0., (time.monotonic() if now is None else now)-self.started)
        if elapsed >= 1.8:
            return 0., 0., 0., 1., 1., 0.
        # Compress and widen first, then stretch and narrow on the rebound.
        # Reciprocal axes preserve area; this never uniformly shrinks the art.
        strength = {'press': .85, 'shy': .9, 'headpat': 1.15}[self.kind]
        spring = math.exp(-3.8*elapsed)*math.sin(15*elapsed)
        squash = (.30 if self.kind == 'shy' else .09)*strength*spring
        scale_y = math.exp(-squash)
        scale_x = 1/scale_y
        # Lateral wobble peaks later than compression, like a soft body whose
        # head follows the torso. The foot pivot stays planted on the desktop.
        wobble = math.exp(-4.5*elapsed)*math.sin(14*elapsed)
        shear = self.direction*(.065 if self.kind == 'shy' else .025)*strength*wobble
        dx, angle = 0., self.direction*.9*wobble
        if self.kind == 'shy':
            # Lean gently away, then settle back without moving the window.
            shy = math.sin(math.pi*min(1., elapsed/1.8))**2
            dx = -self.direction*3*shy
            angle -= self.direction*1*shy
        return dx, 0., angle, scale_x, scale_y, shear
