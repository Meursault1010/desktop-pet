"""Ambient actions use a shuffled bag so every available pose gets a turn."""
import random
import time
from idle_states import AUTOMATIC_ACTIONS, STATES, posture_for

IDLE_ACTIONS = AUTOMATIC_ACTIONS
SEATED_AMBIENT_ACTIONS = frozenset((
    'eat', 'work', 'play-sit', 'reading-pose-1', 'reading-pose-2',
))


class IdleActions:
    def __init__(self):
        self.next_at = 0
        self.bag = []
        self.current = None
        self.period_key = None
        self.period = None
        self.previous = None
        self.state_bag = []
        self.next_rare_at = 0.
        self.pending_action = None

    @property
    def posture(self):
        return posture_for(self.current[0]) if self.current else 'stand'

    def eligible(self):
        # Scheduled sleep has its own continuous state and wake cooldown.
        # Never re-enter the legacy sleep lottery while recently awakened.
        pool = self.period.get('only', IDLE_ACTIONS) if self.period else IDLE_ACTIONS
        preferred = self.period['preferred'] if self.period else ()
        return tuple(dict.fromkeys(key for key in (*pool, *preferred) if key in IDLE_ACTIONS))

    def play(self, player, key, now, skip_entry=False, entry_only=False, exit_only=False):
        player.play(key, now=now)
        action = player.action
        if action.get('ground_idle'):
            # Lengthen neutral rests, never blinks or the entry/rise section.
            base = 4 if key == 'prone-rest' else 3
            durations = list(action['durations'])
            slots = [i for i, frame in enumerate(player.frame_order) if frame == base and 3 <= i < len(durations)-3]
            extra = max(0, random.uniform(24, 38)*1000-sum(durations))
            for slot in slots:
                durations[slot] += extra/max(1, len(slots))
            if entry_only:
                player.frame_order = [0, 1, 2, 3]
                durations = [*durations[:3], random.uniform(900, 1400)]
            elif exit_only:
                player.frame_order = [3, *player.frame_order[-3:]]
                durations = [random.uniform(700, 1100), *durations[-3:]]
            elif skip_entry:
                # A seated story pose already supplies the entry. Start from
                # the neutral seated keyframe and keep the randomized idle loop.
                player.frame_order = [player.frame_order[3], *player.frame_order[4:]]
                durations = [durations[3], *durations[4:]]
            player.action = dict(action, durations=durations)
        elif action['frames'] == 1:
            # Static reading poses still receive the continuous breathing warp.
            player.action = dict(action, durations=[random.uniform(18, 28)*1000])
        duration = sum(player.action['durations'])/1000
        self.current = (key, now, 0., duration)
        return duration

    def defer(self, now, activity='默认'):
        self.next_at = now + random.uniform(*{
            '少动': (22, 34), '默认': (12, 22), '活跃': (9, 16)
        }[activity]) * (self.period['pace'] if self.period else 1)

    def set_period(self, period):
        if self.period_key != period['key']:
            self.bag = []
            self.state_bag = []
            self.period_key = period['key']
        self.period = period

    def choose(self, available):
        # Expressive reactions are ambient flavor, not emotional inference.
        # Keep them rare and separated so they never dominate everyday poses.
        rare = [key for key in ('afraid', 'angry') if key in available]
        if rare and time.monotonic() >= self.next_rare_at and random.random() < .006:
            self.next_rare_at = time.monotonic() + random.uniform(900, 1500)
            return random.choice(rare)
        self.bag = [key for key in self.bag if key in available]
        if not self.bag:
            pool = self.eligible()
            preferred = self.period['preferred'] if self.period else ()
            # Weight the order, not the number of copies: every pose gets one
            # turn before a new round, while time-of-day favourites appear early.
            self.bag = [key for key in pool if key in available]
            self.bag.sort(key=lambda key: random.random() ** (1/(3 if key in preferred else 1)))
        if not self.bag:
            return None
        # Choose posture first, then an unused action in that posture. This
        # prevents the larger standing pool from hiding sitting/prone states.
        self.state_bag = [state for state in self.state_bag
                          if any(posture_for(key) == state for key in self.bag)]
        if not self.state_bag:
            preferred = self.period['preferred'] if self.period else ()
            self.state_bag = [state for state in STATES
                              if any(posture_for(key) == state for key in self.bag)]
            self.state_bag.sort(key=lambda state: random.random() **
                                (1/(3 if any(posture_for(key) == state for key in preferred) else 1)))
        posture = self.state_bag.pop()
        # Do not repeat the same pose when another is available in this cycle.
        candidates = [i for i, key in enumerate(self.bag) if posture_for(key) == posture]
        index = next((i for i in reversed(candidates) if self.bag[i] != self.previous), candidates[-1])
        self.previous = self.bag.pop(index)
        return self.previous

