"""Deterministic frame scheduling shared by desktop actions (no image dependencies)."""
import json
import math
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

    def play(self, action_id, loop=False, speed=1.0, now=None):
        if not isinstance(action_id,str) or action_id not in catalog():
            raise ValueError('未知动作')
        if type(loop) is not bool or type(speed) not in (int,float) or not math.isfinite(speed) or not .25<=speed<=2:
            raise ValueError('动作播放参数不正确')
        self.action=catalog()[action_id]
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
            if elapsed<duration: return i
            elapsed-=duration
        return len(durations)-1
