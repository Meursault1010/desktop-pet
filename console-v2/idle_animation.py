"""Non-looping idle clips driven by monotonic time; independent of movement RNG."""
import random
import time

MOTION_FRAMES = 64
MOTION_SECONDS = 4.2


def motion_phase(elapsed):
    """Continuous layer never waits for a blink or a movement decision."""
    position = (elapsed % MOTION_SECONDS) / MOTION_SECONDS * MOTION_FRAMES
    index = int(position)
    return index, (index + 1) % MOTION_FRAMES, position - index


class IdleAnimation:
    def __init__(self, rng=None, now=None):
        self.rng = rng if rng is not None else random.Random()
        self.reset(time.monotonic() if now is None else now)

    def reset(self, now):
        self.frame = 1
        self.clip = []
        self.clip_start = now
        self.last_update = now
        self.next_blink = now + self.rng.uniform(2.8, 6.8)

    def blink_clip(self):
        closed = self.rng.uniform(.085, .14)
        clip = [(4, .065), (10, closed), (6, .08)]
        if self.rng.random() < .20:
            clip += [(1, self.rng.uniform(.12, .22)), (10, self.rng.uniform(.075, .12)), (11, .08)]
        return clip

    def update(self, now):
        # Movement pause/quiet mode must not freeze the character's visual idle.
        # Only a hidden/suspended timer gap should restart the schedule.
        if now - self.last_update > 1.0:
            self.reset(now)
            return self.frame
        self.last_update = now
        if self.clip:
            elapsed = now - self.clip_start
            for frame, duration in self.clip:
                if elapsed < duration:
                    self.frame = frame
                    return frame
                elapsed -= duration
            self.clip = []
            self.frame = 1
        if now >= self.next_blink:
            self.clip = self.blink_clip()
            self.clip_start = now
            self.next_blink = now + sum(d for _, d in self.clip) + self.rng.uniform(2.8, 6.8)
            self.frame = self.clip[0][0]
        return self.frame
