"""Time-based throw physics in logical desktop pixels; independent of Qt."""
import math
from collections import deque


class PointerVelocity:
    def __init__(self):
        self.samples = deque(maxlen=32)

    def reset(self, x, y, now):
        self.samples.clear()
        self.add(x, y, now)

    def add(self, x, y, now):
        if self.samples and now <= self.samples[-1][0]:
            return
        self.samples.append((now, x, y))
        while len(self.samples) > 2 and now-self.samples[0][0] > .12:
            self.samples.popleft()

    def release(self, x, y, now):
        if not self.samples or now-self.samples[-1][0] > .1:
            return (0., 0.)
        self.add(x, y, now)
        recent = [s for s in self.samples if now-s[0] <= .12]
        if len(recent) < 2:
            return (0., 0.)
        # Least squares suppresses noise from uneven mouse event delivery.
        mean = sum(s[0]-now for s in recent)/len(recent)
        denominator = sum((s[0]-now-mean)**2 for s in recent)
        if denominator < .0001:
            return (0., 0.)
        velocity = tuple(sum((s[0]-now-mean)*s[axis] for s in recent)/denominator
                         for axis in (1, 2))
        speed = math.hypot(*velocity)
        return tuple(v*min(1., 1600/max(1., speed)) for v in velocity)


class PetPhysics:
    def __init__(self):
        self.cancel()

    def cancel(self):
        self.active = False
        self.flying = False
        self.x = self.y = self.vx = self.vy = 0.
        self.age = 0.
        self.impact_age = 10.
        self.impact = None
        self.strength = 0.
        self.collision_count = 0
        self.recovery = 0.

    def launch(self, position, velocity, scale=1.):
        self.cancel()
        self.active = self.flying = True
        self.x, self.y = position
        self.vx, self.vy = velocity
        self.scale = scale

    def hit(self, kind, speed):
        self.impact, self.impact_age = kind, 0.
        incoming = min(1., abs(speed)/(700*self.scale))
        # A later fall may gain speed again; visual energy must still decay
        # throughout this throw instead of restarting the full reaction.
        self.strength = incoming if not self.collision_count else min(incoming, self.strength*.42)
        self.collision_count += 1

    def step(self, dt, bounds, on_segment=None):
        """bounds is (left, top, right, floor) for the window origin.

        Return True exactly once after the final landing has recovered.
        Fixed maximum substeps prevent tunnelling and frame-rate dependence.
        """
        if not self.active:
            return False
        dt = max(0., min(.1, dt))
        count = max(1, math.ceil(dt*240))
        h = dt/count
        left, top, right, floor = bounds
        right, floor = max(left, right), max(top, floor)
        for _ in range(count):
            self.age += h
            self.impact_age += h
            if not self.flying:
                self.recovery += h
                if self.recovery >= .85:
                    self.active = False
                    return True
                continue
            self.vy += 1500*self.scale*h
            self.vx *= math.exp(-.22*h)
            previous = (self.x, self.y)
            self.x += self.vx*h
            self.y += self.vy*h
            # Inspect every substep before screen reflection changes direction.
            # A successful grip consumes the throw immediately.
            if on_segment is not None and on_segment(previous, (self.x, self.y)):
                return False
            if self.x < left or self.x > right:
                side = 'left' if self.x < left else 'right'
                if (self.vx < 0 and side == 'left') or (self.vx > 0 and side == 'right'):
                    self.hit(side, self.vx)
                    self.vx *= -.58
                self.x = max(left, min(right, self.x))
            if self.y < top:
                self.y = top
                if self.vy < 0:
                    self.hit('ceiling', self.vy)
                    self.vy *= -.35
            if self.y >= floor:
                self.y = floor
                if self.vy > 0:
                    speed = self.vy
                    if speed > 130*self.scale:
                        self.hit('floor', speed)
                        self.vy *= -.38
                        self.vx *= .72
                    else:
                        self.vy = 0.
                if self.vy == 0:
                    self.vx *= math.exp(-10*h)
                    if abs(self.vx) < 18*self.scale:
                        self.vx = 0.
                        self.flying = False
                        self.recovery = 0.
                        # Settling is not a new collision: keep the last gentle
                        # recovery rather than inventing another impact impulse.
        return False

    def transform(self):
        """Small volume-preserving jelly deformations; never resize the sprite."""
        t = self.impact_age
        spring = math.exp(-8*t)*math.cos(15*t)*self.strength if t < 1 else 0.
        # Authored impact poses already squash; add only a small elastic finish.
        squash = .025*spring
        if self.impact in ('left', 'right'):
            sx, sy = math.exp(-squash), math.exp(squash)
            angle = (1 if self.impact == 'left' else -1)*.8*spring
        else:
            sx, sy = math.exp(squash), math.exp(-squash)
            angle = 0.
        if self.flying:
            attenuation = 1 if not self.collision_count else self.strength
            angle += max(-2.5, min(2.5, self.vx/(350*self.scale)))*attenuation
        return angle, sx, sy

    def animation_frame(self):
        """Return the authored physics clip and frame for the current impact."""
        if not self.active:
            return None
        clips = {
            'left': 'impact-left', 'right': 'impact-right',
            'ceiling': 'impact-ceiling', 'floor': 'impact-floor',
        }
        impact_clip = clips.get(self.impact)
        if impact_clip and self.collision_count:
            # Do not replay large authored crouch/squash drawings on every
            # bounce. Small contacts use only the mild recovery expressions;
            # the final contacts retain one stable silhouette.
            if self.collision_count >= 2 or self.strength < .12:
                return impact_clip, 7
            return impact_clip, 6 if self.impact_age < .18 else 7
        # Frames 0-1 anticipate contact, which is already resolved by the time
        # hit() fires. Start on the contact pose in the same rendered tick.
        if impact_clip and (self.impact_age < .78 or not self.flying):
            frame = 2
            elapsed = self.impact_age
            for duration in (.07, .10, .13, .16, .18):
                if elapsed < duration:
                    break
                elapsed -= duration
                frame += 1
            return impact_clip, frame
        # Play the launch once, then keep its settled airborne silhouette.
        # Reversing distinct drawings made the body look like it was twitching.
        frame = min(11, int(self.age / .15))
        return 'throw-flight', frame
