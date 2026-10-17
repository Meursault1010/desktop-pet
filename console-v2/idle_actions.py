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

    def defer(self, now, activity='默认'):
        self.next_at = now + random.uniform(*{
            '少动': (28, 45), '默认': (14, 26), '活跃': (8, 16)
        }[activity])

    def choose(self, available):
        self.bag = [key for key in self.bag if key in available]
        if not self.bag:
            self.bag = [key for key in IDLE_ACTIONS if key in available]
            random.shuffle(self.bag)
        return self.bag.pop() if self.bag else None

