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
    # The last two authored flight cells are a directional brace, not a
    # neutral airborne pose. Travel through A/B and the relaxed airborne
    # sequence, then retrace it instead of freezing on the reaching arm.
    FLIGHT_FRAMES = tuple(range(10)) + tuple(range(8, 0, -1))
    FLOOR_RESTITUTION = .60  # About 36% of the previous bounce height.
    FLOOR_CONTACT_TIME = .045
    RECOVERY_TIME = .96

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
        self.anticipation = None
        self.flight_phase = 0.
        self.animation_speed = 1.
        self.contact_hold = 0.

    def launch(self, position, velocity, scale=1.):
        self.cancel()
        self.active = self.flying = True
        self.x, self.y = position
        self.vx, self.vy = velocity
        self.scale = scale

    def hit(self, kind, speed):
        self.impact, self.impact_age = kind, 0.
        self.anticipation = None
        incoming = min(1., abs(speed)/(700*self.scale))
        # Keep small jelly feedback, without extinguishing it after two hits.
        self.strength = incoming if not self.collision_count else min(incoming, self.strength*.85)
        self.collision_count += 1
        self.contact_hold = self.FLOOR_CONTACT_TIME if kind == 'floor' else 0.

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
                self.vx *= math.exp(-10*h)
                self.x = max(left, min(right, self.x+self.vx*h))
                if self.recovery >= self.RECOVERY_TIME:
                    self.vx = 0.
                    self.active = False
                    return True
                continue
            # Slow the *animation* progressively; do not restart its sequence
            # on a bounce or confuse pose playback with physical velocity.
            target_speed = max(.35, .84**self.collision_count)
            previous_speed = self.animation_speed
            self.animation_speed += (target_speed-self.animation_speed)*(1-math.exp(-h/.14))
            if self.contact_hold > 0:
                self.contact_hold = max(0., self.contact_hold-h)
                continue
            self.flight_phase += h*(previous_speed+self.animation_speed)/(.18*2)
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
                        self.vy *= -self.FLOOR_RESTITUTION
                        self.vx *= .72
                    else:
                        self.hit('floor', speed)
                        self.vy = 0.
                        self.flying = False
                        self.recovery = 0.
        self.anticipation = self._predict_impact(bounds) if self.flying else None
        return False

    def _predict_impact(self, bounds):
        """Predict a screen contact within 55 ms for a one-frame brace cue."""
        if self.collision_count >= 2 or (self.collision_count and self.impact_age < .12):
            return None
        left, top, right, floor = bounds
        x, y, vx, vy = self.x, self.y, self.vx, self.vy
        h = 1/240
        for index in range(1, 14):
            vy += 1500*self.scale*h
            vx *= math.exp(-.22*h)
            x += vx*h
            y += vy*h
            if x <= left and vx < 0:
                return ('left', index*h)
            if x >= right and vx > 0:
                return ('right', index*h)
            if y <= top and vy < 0:
                return ('ceiling', index*h)
            if y >= floor and vy > 130*self.scale:
                return ('floor', index*h)
        return None

    def transform(self):
        """Small volume-preserving jelly deformations; never resize the sprite."""
        t = self.impact_age
        fade = max(0., 1-t/.22)
        spring = math.exp(-10*t)*math.cos(22*t)*self.strength*fade
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
        """Contact poses stay at contact; every airborne leg uses flight art."""
        if not self.active:
            return None
        if not self.flying:
            # C: sit on contact, relax the knees, lower the feet and stand.
            # Authored recovery avoids dissolving unrelated PNG silhouettes.
            for frame, end in ((2, .10), (3, .18), (2, .26), (1, .38),
                               (5, .54), (6, .72), (7, self.RECOVERY_TIME)):
                if self.recovery < end:
                    return 'impact-floor', frame
            return 'impact-floor', 7
        if self.contact_hold > 0:
            return 'impact-floor', 2
        if self.anticipation is not None and self.anticipation[0] != 'floor':
            kind, time_to_hit = self.anticipation
            clip = {'left': 'impact-left', 'right': 'impact-right',
                    'ceiling': 'impact-ceiling', 'floor': 'impact-floor'}[kind]
            return clip, 1 if self.collision_count == 0 and time_to_hit <= .028 else 0
        clips = {
            'left': 'impact-left', 'right': 'impact-right',
            'ceiling': 'impact-ceiling', 'floor': 'impact-floor',
        }
        impact_clip = clips.get(self.impact)
        if impact_clip and self.impact != 'floor' and self.impact_age < .04:
            return impact_clip, 2 if self.impact_age < .02 else 3
        return 'throw-flight', self.FLIGHT_FRAMES[int(self.flight_phase) % len(self.FLIGHT_FRAMES)]
