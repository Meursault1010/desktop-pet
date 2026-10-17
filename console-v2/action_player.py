"""Deterministic frame scheduling shared by desktop actions (no image dependencies)."""
import json
import math
import random
import time
from functools import lru_cache
from pathlib import Path

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

    def play(self, action_id, loop=False, speed=1.0, now=None):
        if not isinstance(action_id,str) or action_id not in catalog():
            raise ValueError('未知动作')
        if type(loop) is not bool or type(speed) not in (int,float) or not math.isfinite(speed) or not .25<=speed<=2:
            raise ValueError('动作播放参数不正确')
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
        self.loop=loop; self.speed=speed
        self.started=time.monotonic() if now is None else now

    def stop(self):
        self.action=None

    def frame(self, now=None):
        if self.action is None: return None
        elapsed=max(0,((time.monotonic() if now is None else now)-self.started)*1000*self.speed)
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


def lazy_roll_timeline(action, rng=random):
    """Keep rotational continuity; vary complete cycles, never shuffle angles."""
    cycles = rng.randint(2, 3)
    order = []
    durations = []
    for cycle in range(cycles):
        tempo = rng.uniform(.95, 1.15)
        # Last pose equals the first: omit the duplicate between full turns.
        indices = range(12 if cycle == cycles-1 else 11)
        for index in indices:
            order.append(index)
            durations.append(round(action['durations'][index]*tempo))
    durations[0] += rng.randint(600, 1200)
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
        durations.extend((rng.randint(400, 850), rng.randint(1400, 2600)))
        if rng.random() < .6:
            order.extend((blink, base))
            durations.extend((rng.randint(100, 160), rng.randint(700, 1500)))
    order.extend(range(action['frames']-3, action['frames']))
    durations.extend(action['durations'][-3:])
    return order, durations
