"""Deterministic frame scheduling shared by desktop actions (no image dependencies)."""
import json
import math
import random
import time
from functools import lru_cache
from pathlib import Path


# Virtual roll frames reuse the existing, approved lowering poses. They are
# resolved only by the renderer; the catalog and original artwork stay intact.
ROLL_ENTRY = (12, 13, 14, 15)
ROLL_ENTRY_DURATIONS = (200, 280, 300, 260)
ROLL_DIRECTION = {'lazy-roll-toward': -1, 'lazy-roll-away': 1}
# Position at each authored pose, rather than elapsed time or frame number.
# The away atlas reverses the turn, so its side-lying holds come first.
ROLL_TRAVEL_PHASE = {
    'lazy-roll-toward': (0., 0., .12, .28, .45, .62, .80, .94, 1., 1., 1., 1.),
    'lazy-roll-away': (0., 0., 0., 0., .06, .20, .38, .55, .72, .88, 1., 1.),
}


def pose_ref(action_id, frame):
    if action_id.startswith('lazy-roll-') and frame in ROLL_ENTRY:
        return 'prone-rest', (0, 1, 2, 4)[frame-12]
    return action_id, frame


# Reading is a posture, not a gesture: lift the book once, then hold it and
# let the eyes drift between the page and the viewer before settling out.
READ_SETTLE = 12
READ_EYES_UP = (12, 20)
READ_EYES_DOWN = (27, 32)


FAST_TEMPO = frozenset(('celebrate', 'clicked', 'afraid', 'angry'))
GENTLE_TEMPO = frozenset((
    'sleep-enter', 'sleep-wake', 'read', 'tea', 'sit-neat', 'sit-relaxed',
    'sit-swing', 'prone-chin', 'prone-rest', 'yawn', 'stretch', 'comb',
    'wave', 'curtsy', 'gaze-far', 'listen', 'warm-hands', 'star-wish',
    'hair-tuck', 'hum', 'wait',
))


def transition_window(action, duration):
    # Long expression holds remain holds. Spend only the end of a slot moving
    # towards the next pose, then arrive exactly at that pose's start time.
    if action.get('lazy_roll'):
        return min(duration*.85, 340)
    action_id = action.get('id')
    if action_id in FAST_TEMPO:
        return min(duration*.55, 120)
    if action_id in GENTLE_TEMPO:
        return min(duration*.85, 300)
    return min(duration*.8, 220)


def transition_phase(action, duration, elapsed, frame, target_frame):
    # Rolling is continuous rotation: easing to zero at every keyframe creates
    # a stop-motion cadence. Keep end rests, but travel linearly between angles.
    if action.get('lazy_roll') and 0 <= frame <= 10 and 0 <= target_frame <= 11:
        window = min(duration, 520) if frame == 0 else duration
        return max(0., min(1., (elapsed-(duration-window))/window))
    window = transition_window(action, duration)
    t = max(0., min(1., (elapsed-(duration-window))/window))
    return t*t*(3-2*t)

@lru_cache(maxsize=1)
def catalog():
    path=Path(__file__).resolve().parent/'assets/actions/catalog.json'
    return {a['id']:a for a in json.loads(path.read_text(encoding='utf-8'))} if path.exists() else {}

class ActionPlayer:
    def __init__(self):
        self.action=None
        self.started=0
        self.loop=False
        self.speed=1.0
        self.frame_order=None
        self.generation = 0

    def play(self, action_id, loop=False, speed=1.0, now=None):
        if not isinstance(action_id,str) or action_id not in catalog():
            raise ValueError('未知动作')
        if type(loop) is not bool or type(speed) not in (int,float) or not math.isfinite(speed) or not .25<=speed<=2:
            raise ValueError('动作播放参数不正确')
        self.generation += 1
        self.action=catalog()[action_id]
        self.frame_order=None
        if self.action.get('lazy_roll'):
            self.frame_order, durations = lazy_roll_timeline(self.action)
            self.action = dict(self.action, durations=durations)
        if self.action.get('ground_idle'):
            order, durations = ground_idle_timeline(self.action)
            # Own the playback schedule; never mutate the shared catalog.
            self.action = dict(self.action, durations=durations)
            self.frame_order = order
        if self.action.get('dance_rest'):
            self.frame_order,durations=dance_rest_timeline(self.action,random)
            self.action=dict(self.action,durations=durations)
        if self.action.get('reading_idle'):
            self.frame_order, durations = reading_idle_timeline(self.action)
            self.action = dict(self.action, durations=durations)
        self.loop=loop; self.speed=speed
        self.started=time.monotonic() if now is None else now

    def stop(self):
        self.generation += 1
        self.action=None

    def frame(self, now=None):
        if self.action is None: return None
        elapsed=max(0,((time.monotonic() if now is None else now)-self.started)*1000*self.speed)+1e-7
        durations=self.action['durations'];total=sum(durations)
        if elapsed>=total and not self.loop:
            self.stop();return None
        if elapsed>=total:
            loop_start=self.action.get('loop_start',0)
            intro=sum(durations[:loop_start])
            elapsed=intro+(elapsed-total)%(total-intro)
        for i,duration in enumerate(durations):
            if elapsed<duration: return self.frame_order[i] if self.frame_order else i
            elapsed-=duration
        return len(durations)-1

    def motion_sample(self, now=None):
        """Two authored pose references and eased in-between position.

        Pure time sampling: repaint rate never advances the clip, and a loop
        with an intro wraps to loop_start rather than replaying that intro.
        """
        now = time.monotonic() if now is None else now
        if self.frame(now) is None:
            return None
        action = self.action
        durations = action['durations']
        elapsed = max(0, (now-self.started)*1000*self.speed)+1e-7
        total = sum(durations)
        if elapsed >= total:
            intro = sum(durations[:action.get('loop_start', 0)])
            elapsed = intro+(elapsed-total) % (total-intro)
        slot = 0
        while slot < len(durations)-1 and elapsed >= durations[slot]:
            elapsed -= durations[slot]
            slot += 1
        order = self.frame_order or list(range(len(durations)))
        current = pose_ref(action['id'], order[slot])
        if slot+1 == len(order) and not self.loop:
            return current, current, 0.
        following = slot+1 if slot+1 < len(order) else action.get('loop_start', 0)
        target = pose_ref(action['id'], order[following])
        return current, target, transition_phase(action, durations[slot], elapsed,
                                                order[slot], order[following])

    def roll_progress(self, now=None):
        """Normalized lateral travel, synchronized with the authored roll cycles."""
        if self.action is None or not self.action.get('lazy_roll'):
            return None
        now = time.monotonic() if now is None else now
        elapsed = max(0, (now-self.started)*1000*self.speed)
        durations = self.action['durations']
        if elapsed >= sum(durations):
            return 1.
        slot = 0
        while slot < len(durations)-1 and elapsed >= durations[slot]:
            elapsed -= durations[slot]
            slot += 1
        order = self.frame_order or []
        cycle_count = sum(frame == 0 for frame in order[4:])
        if cycle_count <= 0:
            return 0.
        cycle = -1
        positions = []
        for index, frame in enumerate(order):
            if index < 4:
                positions.append(0.)
                continue
            if frame == 0:
                cycle += 1
            phase = ROLL_TRAVEL_PHASE[self.action['id']][frame]
            positions.append((cycle + phase)/cycle_count)
        current = positions[slot]
        if slot+1 == len(positions):
            return min(1., max(0., current))
        t = transition_phase(self.action, durations[slot], elapsed,
                             order[slot], order[slot+1])
        return min(1., max(0., current+(positions[slot+1]-current)*t))

    def upcoming_pairs(self, now=None):
        """Prefetch a small lookahead without advancing/stopping the clip."""
        if self.action is None:
            return []
        elapsed = max(0, ((time.monotonic() if now is None else now)-self.started)*1000*self.speed)
        durations = self.action['durations']
        total = sum(durations)
        if elapsed >= total:
            if not self.loop:
                return []
            intro = sum(durations[:self.action.get('loop_start',0)])
            elapsed = intro+(elapsed-total) % (total-intro)
        slot = 0
        while slot < len(durations)-1 and elapsed >= durations[slot]:
            elapsed -= durations[slot]
            slot += 1
        order = self.frame_order or list(range(len(durations)))
        pairs = []
        for _ in range(3):
            following = slot+1
            if following == len(order):
                if not self.loop:
                    break
                following = self.action.get('loop_start',0)
            pairs.append((pose_ref(self.action['id'],order[slot]),
                          pose_ref(self.action['id'],order[following])))
            slot = following
        return pairs


def lazy_roll_timeline(action, rng=random, cycles=None):
    """Keep rotational continuity; vary complete cycles, never shuffle angles."""
    cycles = rng.randint(2, 3) if cycles is None else cycles
    order = list(ROLL_ENTRY)
    durations = list(ROLL_ENTRY_DURATIONS)
    for cycle in range(cycles):
        tempo = rng.uniform(.98, 1.08)
        # Last pose equals the first: omit the duplicate between full turns.
        indices = range(12 if cycle == cycles-1 else 11)
        for index in indices:
            order.append(index)
            durations.append(round(action['durations'][index]*tempo))
    durations[len(ROLL_ENTRY)] += rng.randint(600, 1200)
    durations[-1] += rng.randint(900, 1800)
    return order, durations


def ground_idle_timeline(action, rng=random):
    """Enter once, make spaced small gestures, recover once; reroll per play."""
    base, blink, gestures = {
        'sit-neat': (3, 6, (4, 5, 7, 8)),
        'sit-relaxed': (3, 6, (4, 7, 8)),
        'sit-swing': (3, 6, (4, 5, 7, 8)),
        'prone-chin': (3, 5, (4, 6, 7, 8)),
        'prone-rest': (4, 5, (6, 7, 8)),
    }[action['id']]
    order = [0, 1, 2, base]
    durations = list(action['durations'][:3]) + [rng.randint(1000, 2200)]
    for gesture in rng.sample(gestures, rng.randint(2, len(gestures))):
        # Always return to a neutral pose between expressions: no random jumps
        # from a head tilt to a foot kick or repeated closed-eye frames.
        order.extend((gesture, base))
        # Half-lidded frames are a blink lead-in, not a long frozen expression.
        durations.extend((rng.randint(140, 220) if gesture == 4 else rng.randint(350, 650),
                          rng.randint(1400, 2600)))
        if rng.random() < .6:
            order.extend((blink, base))
            durations.extend((rng.randint(100, 160), rng.randint(700, 1500)))
    order.extend(range(action['frames']-3, action['frames']))
    durations.extend(action['durations'][-3:])
    return order, durations


def reading_idle_timeline(action, rng=random, target=None):
    """Lift the book once, then stay reading with slow gaze drifts.

    The authored clip is a 3s gesture. As an idle it keeps the same drawings
    but holds each reading pose for seconds, so the cover settle, the dwell and
    the lift can be rerolled per play without ever replaying the entry.
    """
    durations = action['durations']
    last = action['frames']-1
    order = list(range(READ_SETTLE))
    times = list(durations[:READ_SETTLE])
    # Settle straight into the page; the dwell never lifts the cover again.
    order.extend(range(READ_SETTLE, READ_EYES_DOWN[0]+1))
    times.extend(durations[READ_SETTLE:READ_EYES_DOWN[0]+1])
    target = rng.uniform(17000, 27000) if target is None else target
    while sum(times) < target:
        down = min(last, rng.randint(*READ_EYES_DOWN))
        up = rng.randint(*READ_EYES_UP)
        order.append(down)
        times.append(rng.randint(2400, 4600))
        order.extend(range(down-1, up-1, -1))
        times.extend([rng.randint(85, 115)]*(down-up))
        order.append(up)
        times.append(rng.randint(1400, 2800))
        order.extend(range(up+1, down+1))
        times.extend([rng.randint(85, 115)]*(down-up))
    return order, times


def dance_rest_timeline(action, rng=random):
    """Lower once, breathe with sparse blinks, then rise using clean drawings."""
    order=list(range(8));durations=list(action['durations'][:8])
    # Only seated frames enter the rest loop; lowering is never replayed.
    for cycle in range(rng.randint(4,6)):
        order.extend((7,8,7))
        durations.extend((rng.randint(1100,1700),650,rng.randint(700,1100)))
        if cycle%2==1:
            order.extend((9,7));durations.extend((130,750))
    # Use the supported sit-down motion in reverse to stand up before idle.
    order.extend((6,5,4,3,2,1,0))
    durations.extend((350,400,420,380,300,250,350))
    return order,durations
