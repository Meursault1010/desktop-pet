"""Ambient actions use a shuffled bag so every available pose gets a turn."""
import random

IDLE_ACTIONS = ('eat', 'comb',
                'dress', 'leap', 'read', 'stretch', 'tea', 'wait', 'yawn',
                'sit-neat', 'sit-relaxed', 'sit-swing', 'prone-chin', 'prone-rest',
                'lazy-roll-toward', 'lazy-roll-away')


class IdleActions:
    def __init__(self):
        self.next_at = 0
        self.bag = []
        self.current = None
        self.period_key = None
        self.period = None
        self.previous = None

    def defer(self, now, activity='默认'):
        self.next_at = now + random.uniform(*{
            '少动': (40, 65), '默认': (24, 40), '活跃': (18, 30)
        }[activity]) * (self.period['pace'] if self.period else 1)

    def set_period(self, period):
        if self.period_key != period['key']:
            self.bag = []
            self.period_key = period['key']
        self.period = period

    def choose(self, available):
        self.bag = [key for key in self.bag if key in available]
        if not self.bag:
            pool = self.period.get('only', IDLE_ACTIONS) if self.period else IDLE_ACTIONS
            self.bag = [key for key in pool if key in available]
            if self.period:
                self.bag += [key for key in self.period['preferred'] if key in available for _ in range(2)]
            random.shuffle(self.bag)
        if not self.bag:
            return None
        # Do not repeat the same pose when another is available in this cycle.
        index = next((i for i in range(len(self.bag)-1, -1, -1) if self.bag[i] != self.previous), -1)
        self.previous = self.bag.pop(index)
        return self.previous

