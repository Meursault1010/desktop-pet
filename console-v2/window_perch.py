"""Shimeji-style foreground-window perch, using read-only window bounds."""
import math
import os
import random
import time

from PySide6.QtGui import QCursor, QGuiApplication

from edge_attachment import logical_surface
from edge_geometry import candidates
from window_edges import inspect_foreground


class WindowPerch:
    def __init__(self, pet, edge):
        self.pet = pet
        self.edge = edge
        self.enabled = True
        self.active = False
        self.message = '偶尔会去前台窗口上沿坐一会儿'
        self.error = ''
        self.next_at = time.monotonic()+random.uniform(120, 240)
        self.variant = random.randrange(4)
        self.attached = False
        self.attached_started = None
        self.leaping = False
        self.leap_generation = None
        self.leap_started = 0.
        self.leap_duration = .6
        self.leap_from = (0., 0.)
        self.candidate = None
        pet.window_perch = self

    def excluded(self):
        return (os.getppid(), int(os.environ.get('PET_CONTROL_PID', '0')))

    def snapshot(self):
        return {'enabled': self.enabled, 'active': self.active, 'leaping': self.leaping,
                'phase': 'leap' if self.leaping else 'perched' if self.attached else 'idle',
                'message': self.message, 'error': self.error}

    def tick(self, now=None):
        now = time.monotonic() if now is None else now
        self.enabled = bool(self.pet.preferences.autonomous_windows)
        if self.leaping:
            self._advance_leap(now)
            return
        if self.attached:
            if not self.edge.active or self.edge.started != self.attached_started:
                self.attached = False
                self.attached_started = None
                self.active = False
                self.message = '已经离开窗口'
            elif not self._allowed():
                self.release(now, 30)
                return
        if self.active != self.attached:
            self.active = self.attached
        if not self._allowed() or not self.enabled or now < self.next_at:
            return
        if self.try_perch(now):
            self.next_at = now+random.uniform(120, 240)
        else:
            self.next_at = now+random.uniform(35, 60)

    def manual(self, now=None):
        now = time.monotonic() if now is None else now
        if self.leaping or self.attached:
            return True
        if not self._allowed(manual=True):
            raise ValueError('请先结束拖动、睡眠、专注或暂停状态')
        if not self.try_perch(now):
            raise ValueError(self.error or '当前没有可以停靠的前台窗口')
        self.next_at = now+random.uniform(120, 240)
        return True

    def cancel(self, now=None):
        now = time.monotonic() if now is None else now
        self.release(now, 0)

    def release(self, now=None, cooldown=20):
        now = time.monotonic() if now is None else now
        if self.leaping:
            player = self.pet.state.action_player
            if self.leap_generation is not None and player.generation == self.leap_generation:
                player.stop()
            self.leaping = False
            self.leap_generation = None
            self.candidate = None
        if self.attached and self.edge.active and self.edge.started == self.attached_started:
            self.edge.release(cooldown=cooldown)
        self.attached = False
        self.attached_started = None
        if self.active:
            self.active = False
            self.message = '已经离开窗口'
            self.pet.state_changed.emit()

    def _allowed(self, manual=False):
        pet = self.pet
        pref = pet.preferences
        state = pet.state
        return (pet.isVisible() and pet.drag_origin is None and not pet.presence.active
                and not state.sleep.active and not state.sleep.transitioning
                and not state.physics.active and not state.walking
                and state.action_player.action is None
                and not pref.quiet and not pref.paused and pref.random_movement
                and (manual or pref.autonomous_play)
                and not bool(getattr(pet.controller, 'quick_pending', None))
                and not (state.icon_sleep and state.icon_sleep.target)
                and not (state.edge_attachment and state.edge_attachment.active)
                and not (state.patrol and (state.patrol.active or state.patrol.exploring))
                and not (state.music and state.music.active)
                and not (getattr(pet, 'focus', None) and pet.focus.active))

    def try_perch(self, now):
        surface = inspect_foreground(self.excluded())
        if surface is None or surface.fullscreen:
            self.error = '当前没有可停靠的前台窗口'
            return False
        try:
            rect, area, screen = logical_surface(surface, QGuiApplication.screens())
        except (ValueError, IndexError):
            self.error = '无法读取窗口边界'
            return False
        pet = self.pet
        if screen != pet.screen():
            self.error = '前台窗口不在宠物所在的显示器'
            return False
        size = (pet.width(), pet.height())
        origin = (pet.x(), pet.y())
        choices = [landing for _, landing in candidates(
            rect, area, size, self.edge.poses.bounds, origin, self.variant, ())
            if landing.kind == 'top']
        if not choices:
            self.error = '这个窗口上方没有足够的停靠空间'
            return False
        pointer = QCursor.pos()
        choices = [landing for landing in choices
                   if math.hypot(pointer.x()-landing.anchor[0],
                                 pointer.y()-landing.anchor[1]) >= max(120, pet.height()*.65)]
        if not choices:
            self.error = '指针正停在窗口上沿'
            return False
        landing = min(choices, key=lambda item: math.hypot(
            item.position[0]-origin[0], item.position[1]-origin[1]))
        distance = math.hypot(landing.position[0]-origin[0], landing.position[1]-origin[1])
        if distance < 24 or distance > max(520, pet.width()*3):
            self.error = '附近没有合适的窗口上沿'
            return False
        if origin[1]-landing.position[1] > max(280, pet.height()*1.6):
            self.error = '窗口上沿太高了'
            return False
        self.candidate = (landing, surface, screen, rect)
        self.error = ''
        self.leap_from = origin
        self.leap_started = now
        self.leap_duration = max(.45, min(.85, distance/520))
        player = pet.state.action_player
        try:
            player.play('play-climb-up', loop=True, speed=.95, now=now)
        except ValueError:
            self.candidate = None
            self.error = '缺少攀爬动作'
            return False
        self.leap_generation = player.generation
        pet.state.walking = False
        pet.state.travel_target = None
        pet.state.travel_position = None
        pet.state.gait_until = 0
        pet.state.ambient.current = None
        pet.state.ambient.defer(now, pet.preferences.activity)
        self.leaping = True
        self.active = True
        self.message = '去前台窗口上沿坐一会儿'
        pet.update()
        pet.state_changed.emit()
        return True

    def _advance_leap(self, now):
        if (not self.leaping or self.candidate is None or self.pet.drag_origin is not None
                or not self.pet.isVisible() or self.pet.presence.active
                or self.pet.state.physics.active or self.pet.preferences.quiet
                or self.pet.preferences.paused):
            self.release(now, 5)
            return
        progress = min(1., max(0., (now-self.leap_started)/self.leap_duration))
        eased = progress*progress*(3-2*progress)
        x0, y0 = self.leap_from
        x1, y1 = self.candidate[0].position
        distance = math.hypot(x1-x0, y1-y0)
        arc = min(52., distance*.14)*math.sin(math.pi*eased)
        self.pet.move(round(x0+(x1-x0)*eased), round(y0+(y1-y0)*eased-arc))
        self.pet.state.position_x = float(self.pet.x())
        if progress < 1:
            self.pet.update()
            return
        candidate = self.candidate
        self.candidate = None
        self.leaping = False
        self.leap_generation = None
        if not self.edge.attach(candidate, autonomous=True):
            self.release(now, 15)
            return
        self.attached = True
        self.attached_started = self.edge.started
        self.edge.message = '窗口上沿 · 陪你待一会儿'
        self.message = '在窗口上沿休息，跟着窗口移动'
        self.active = True
        self.pet.state_changed.emit()
