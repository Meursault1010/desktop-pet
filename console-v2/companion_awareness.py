"""A quiet return greeting based only on Windows' last-input timestamp."""
import random
import time

from input_activity import idle_seconds

AWAY_SECONDS = 20*60
RETURN_SECONDS = 4
COOLDOWN = 60*60
LINES = ('你回来啦。我刚刚有好好待着。',
         '欢迎回来，先坐下来缓一缓吧。',
         '听见你回来了。要不要先喝口水？',
         '我一直在这里。慢慢来就好。')


class CompanionAwareness:
    def __init__(self, pet, memory=None, idle=idle_seconds):
        self.pet = pet
        self.memory = memory
        self.idle = idle
        self.away = False
        self.away_since = None
        self.last_greeting = -float('inf')
        self.last_check = 0.

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if now-self.last_check < 10:
            return None
        self.last_check = now
        try:
            seconds = self.idle()
        except OSError:
            return None
        if seconds is None:
            return None
        if seconds >= AWAY_SECONDS:
            if not self.away:
                self.away = True
                self.away_since = now
            return None
        if not self.away or seconds > RETURN_SECONDS:
            return None
        self.away = False
        if now-self.last_greeting < COOLDOWN:
            return None
        return self.greet(now)

    def greet(self, now=None):
        now = time.monotonic() if now is None else now
        pet = self.pet
        state = pet.state
        focus = getattr(pet, 'focus', None)
        perch = getattr(pet, 'window_perch', None)
        if (not pet.isVisible() or pet.drag_origin is not None or pet.presence.active
                or state.sleep.active or state.sleep.transitioning
                or state.physics.active
                or bool(state.icon_sleep and state.icon_sleep.target)
                or bool(state.edge_attachment and state.edge_attachment.active)
                or bool(state.music and state.music.active)
                or bool(perch and (perch.attached or perch.leaping))
                or pet.preferences.quiet or pet.preferences.paused
                or not pet.preferences.greeting
                or not pet.preferences.autonomous_speech
                or (focus is not None and focus.active)
                or bool(getattr(pet.controller, 'quick_pending', None))):
            return None
        patrol = state.patrol
        if (state.action_player.action is None and not state.walking
                and not (patrol and (patrol.active or patrol.exploring))):
            state.action_player.play('wave', speed=.9)
            state.walking = False
            state.ambient.current = None
            state.ambient.defer(now, pet.preferences.activity)
        pet.bubble.say(random.choice(LINES), 'ambient')
        if self.memory is not None:
            self.memory.record('greetings', now=time.time())
        self.last_greeting = now
        pet.state_changed.emit()
        return 'return'
