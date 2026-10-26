"""Focus companion: quiet presence, break gestures and optional click-through."""
import time
from dataclasses import replace

from PySide6.QtCore import Qt

from action_player import catalog

FOCUS_HOLD_MS = 10*60*1000


class FocusCompanion:
    def __init__(self, pet, base, memory=None):
        self.pet = pet
        self.base = base
        self.memory = memory
        self.active = False
        self.phase = 'idle'
        self.until = 0.
        self.remaining = 0
        self.click_through = False
        self.focus_started = None
        self.hold_generation = None
        self.break_started = None
        self.break_treat_at = 0.
        self.last_tick = 0.
        self.last_hold_attempt = 0.
        self.sessions = 0
        self.free_generation = None
        pet.focus = self

    def set(self, enabled, phase='focus', remaining=None, now=None):
        now = time.monotonic() if now is None else now
        if not enabled:
            self.end(now)
            return self.snapshot(now)
        phase = 'break' if phase == 'break' else 'focus'
        if remaining is not None:
            self.remaining = max(0, min(24*60*60, int(remaining)))
            self.until = now+self.remaining
        elif not self.active:
            self.remaining = 0
            self.until = 0
        was_active, previous = self.active, self.phase
        self.active = True
        self.phase = phase
        # Preference and click-through flags may hide/show the native window,
        # which ends the current action. Apply them before starting the hold.
        self.sync()
        if not was_active:
            self.sessions += 1
            self.focus_started = now
            self.break_started = None
            self.break_treat_at = 0.
            if phase == 'focus':
                self._begin_focus(now)
            else:
                self._begin_break(now)
        elif previous != phase:
            if phase == 'break':
                self._finish_focus(now)
                self._release_actions()
                self._begin_break(now)
            else:
                self.break_started = self.break_treat_at = None
                self.focus_started = now
                self._begin_focus(now)
        return self.snapshot(now)

    def end(self, now=None):
        now = time.monotonic() if now is None else now
        was_active, phase = self.active, self.phase
        if phase == 'focus':
            self._finish_focus(now)
        self.active = False
        self.phase = 'idle'
        self.until = 0.
        self.remaining = 0
        self.focus_started = None
        self.break_started = None
        self.break_treat_at = 0.
        self._release_actions()
        self._set_click_through(False)
        self.sync()
        if was_active and phase == 'break' and self.base().focus_companion:
            self._play_free('celebrate', now)
        self.pet.state_changed.emit()
        return self.snapshot(now)

    def sync(self):
        base = self.base()
        quiet = self.active and base.focus_companion
        self.pet.apply_preferences(replace(base, quiet=True) if quiet else base)
        self._set_click_through(self.active and self.phase == 'focus'
                                and base.focus_companion and base.focus_click_through)

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        if now-self.last_tick < .5:
            return
        self.last_tick = now
        if not self.active or not self.base().focus_companion:
            return
        if self.until and now >= self.until:
            self.end(now)
            return
        if self.phase == 'focus':
            self._hold_sit(now)
        elif self.phase == 'break':
            if self.break_started is None:
                self.break_started = now
            if self.break_treat_at and now >= self.break_treat_at:
                if self._play_free('tea', now):
                    self.break_treat_at = 0.

    def owns_action(self):
        player = self.pet.state.action_player
        return (self.hold_generation is not None and player.action is not None
                and player.generation == self.hold_generation
                and player.action['id'] == 'sit-neat')

    def owns_free(self):
        player = self.pet.state.action_player
        return (self.free_generation is not None and player.action is not None
                and player.generation == self.free_generation
                and player.action['id'] in ('stretch', 'tea'))

    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        session_minutes = 0
        if self.focus_started is not None:
            session_minutes = max(0, int((now-self.focus_started)//60))
        return {'active': self.active, 'phase': self.phase,
                'remaining': max(0, round(self.until-now)) if self.active and self.until else 0,
                'click_through': self.click_through,
                'enabled': self.base().focus_companion,
                'session_minutes': session_minutes}

    def save_session(self):
        if self.active and self.phase == 'focus':
            self._finish_focus(time.monotonic())

    def _begin_focus(self, now):
        self.pet.wake_icon_sleep()
        self.pet.state.sleep.wake(self.pet, '专注陪伴')
        self._hold_sit(now, force=True)

    def _begin_break(self, now):
        self.break_started = now
        self.break_treat_at = now+60
        self._play_free('stretch', now)

    def _finish_focus(self, now):
        if self.focus_started is None:
            return
        minutes = max(0, int((now-self.focus_started)//60))
        if minutes and self.memory is not None:
            self.memory.record('focus_minutes', minutes)
        self.focus_started = None

    def _hold_sit(self, now, force=False):
        state = self.pet.state
        player = state.action_player
        if state.sleep.active or state.sleep.transitioning:
            return False
        if not force and player.action is not None:
            return False
        if (self.pet.drag_origin is not None or state.physics.active or state.walking
                or self.pet.presence.active
                or bool(state.icon_sleep and state.icon_sleep.target)
                or bool(state.edge_attachment and state.edge_attachment.active)
                or bool(state.patrol and (state.patrol.active or state.patrol.exploring))
                or bool(state.music and state.music.active)):
            return False
        if not force and now-self.last_hold_attempt < 2:
            return False
        self.last_hold_attempt = now
        try:
            player.play('sit-neat', now=now)
        except ValueError:
            return False
        durations = list(catalog()['sit-neat']['durations'][:3])+[FOCUS_HOLD_MS]
        player.action = dict(player.action, durations=durations)
        player.frame_order = [0, 1, 2, 3]
        self.hold_generation = player.generation
        state.walking = False
        state.gait_until = 0
        state.ambient.current = None
        state.ambient.defer(now, self.pet.preferences.activity)
        self.pet.update()
        self.pet.state_changed.emit()
        return True

    def _release_actions(self):
        player = self.pet.state.action_player
        if (player.action is not None
                and player.generation in (self.hold_generation, self.free_generation)):
            player.stop()
        self.hold_generation = None
        self.free_generation = None

    def _play_free(self, action_id, now):
        state = self.pet.state
        if (state.sleep.active or state.sleep.transitioning or state.action_player.action is not None
                or state.walking or self.pet.drag_origin is not None or state.physics.active
                or self.pet.presence.active
                or bool(state.icon_sleep and state.icon_sleep.target)
                or bool(state.edge_attachment and state.edge_attachment.active)
                or bool(state.patrol and (state.patrol.active or state.patrol.exploring))
                or bool(state.music and state.music.active)):
            return False
        try:
            state.action_player.play(action_id, speed=.9, now=now)
        except ValueError:
            return False
        if action_id in ('stretch', 'tea'):
            self.free_generation = state.action_player.generation
        state.walking = False
        state.ambient.current = None
        state.ambient.defer(now, self.pet.preferences.activity)
        self.pet.update()
        self.pet.state_changed.emit()
        return True

    def _set_click_through(self, enabled):
        if enabled == self.click_through:
            return
        self.click_through = enabled
        visible = self.pet.isVisible()
        self.pet.setWindowFlag(Qt.WindowType.WindowTransparentForInput, enabled)
        if visible:
            self.pet.show()
            self.pet.masker.reapply()
