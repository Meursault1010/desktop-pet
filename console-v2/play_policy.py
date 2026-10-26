"""Bounded local play decisions. No window, file-content or input recording."""
from collections import deque


class PlayPolicy:
    def __init__(self):
        self.energy = 75.
        self.curiosity = 35.
        self.motion = deque()
        self.recent = deque(maxlen=6)
        self.icons = {}
        self.stories = {}
        self.failures = {}
        self.visits = {}
        self.streak = 0
        self.quiet_until = 0.

    def remaining(self, now, activity):
        while self.motion and self.motion[0][0] <= now-600:
            self.motion.popleft()
        limit = {'少动': 30., '默认': 60., '活跃': float('inf')}[activity]
        return max(0., limit-sum(seconds for _, seconds in self.motion))

    def advance(self, now, dt, moving=False, asleep=False):
        dt = max(0., min(.1, dt))
        if moving:
            bucket = int(now)
            if self.motion and int(self.motion[-1][0]) == bucket:
                stamp, seconds = self.motion.pop()
                self.motion.append((stamp, seconds+dt))
            else:
                self.motion.append((now, dt))
        self.energy = max(0., min(100., self.energy + dt*(.12 if asleep else -.35 if moving else .025)))
        self.curiosity = min(100., self.curiosity + (0 if asleep else dt*.035))

    def available(self, kind, now, exploring=False, unrestricted=False):
        return ((exploring or now >= self.quiet_until) and now >= self.stories.get(kind, 0)
                and kind not in list(self.recent)[-2:]
                and not (not unrestricted and self.energy < 30 and kind == 'orbit')
                and not (not unrestricted and self.energy < 15 and kind != 'rest'))

    def complete(self, kind, icon_id, now, rest_seconds, *, exploring=False):
        self.recent.append(kind)
        self.stories[kind] = now+(45 if exploring else 480)
        if icon_id is not None:
            self.icons[icon_id] = now+(60 if exploring else 300)
            count, _ = self.visits.get(icon_id, (0, now))
            self.visits[icon_id] = (min(10,count+1),now)
            if len(self.visits) > 64:
                del self.visits[min(self.visits,key=lambda key:self.visits[key][1])]
        self.curiosity = max(0., self.curiosity-20)
        self.streak += 1
        if self.streak >= 2:
            self.quiet_until = now+rest_seconds
            self.streak = 0

    def fail(self, icon_id, now):
        if icon_id is not None:
            self.failures[icon_id] = now+120

    def score(self, icon_id, distance, radius, space, rest, now):
        if now < max(self.icons.get(icon_id, 0), self.failures.get(icon_id, 0)):
            return None
        count = self.visits.get(icon_id, (0,now))[0]
        fresh = 1./(1+count)
        familiar = min(1.,count/3)
        return (.30*max(0., 1-distance/radius)+.25*space+.20*fresh
                +.15*rest+.10*familiar)

    def prune(self, now):
        # Retain only a small amount of non-content, transient desktop memory.
        for mapping in (self.icons, self.stories, self.failures):
            for key, until in list(mapping.items()):
                if until < now-600:
                    del mapping[key]
