"""Scheduled continuous sleep, independent of random idle clips."""
from datetime import datetime
from functools import lru_cache
from pathlib import Path
import json
import math
import time
from action_player import catalog
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap
import cv2
import numpy as np

ASSETS = Path(__file__).resolve().parent/'assets'/'sleep'
MANIFEST = json.loads((ASSETS/'transitions/manifest.json').read_text(encoding='utf-8'))
PLAYBACK = MANIFEST.get('playback', {})
SETTLE_SECONDS = PLAYBACK.get('settle', MANIFEST['settle']['seconds'])
WAKE_SECONDS = PLAYBACK.get('wake', MANIFEST['wake']['seconds'])
WAKE_HOLD_SECONDS = PLAYBACK.get('wake_hold', 0.)
SIZE = tuple(MANIFEST['size'])

# The sleeper lies on the pillow, so a whole-body scale reads as the picture
# inflating: the head and the pillow travel with the chest and the pillow is
# supposed to be pixel exact. The breath is a bulge on the shoulder/chest mass
# instead, with the supported regions guarded to zero.
BREATH_SECONDS = 4.2
BREATH_AMPLITUDE = 5.                       # source px at the crest (screen ±2.5 px)
CHEST = (0.50, 0.535, 0.22, 0.14)           # nx, ny, x spread, y spread
HIP = (0.42, 0.72, 0.22, 0.10)
HIP_FOLLOW = 0.35
# x0, y0, x1, y1: the face and hand resting on the pillow, the pillow itself and
# the shoes on the ground. Guarded regions stay byte-identical while breathing.
GUARDS = ((200, 60, 330, 190), (246, 150, 322, 252), (50, 262, 150, 312))
CONTACT_ROW = 311
FEATHER = 14.


def _guard(shape, box):
    """1 outside the box, ramping to 0 over `FEATHER` px inside it."""
    x0, y0, x1, y1 = box
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    inner = np.minimum.reduce([xx - x0, y1 - yy, x1 - xx, yy - y0])
    return np.clip(inner / FEATHER + .5, 0., 1.)


@lru_cache(maxsize=2)
def breath_field(width, height):
    """Upward chest displacement per unit of breath, in source pixels."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    nx, ny = xx / width, yy / height

    def gauss(cx, cy, sx, sy):
        return np.exp(-((nx - cx) / sx) ** 2) * np.exp(-((ny - cy) / sy) ** 2)

    keep = 1.
    for box in GUARDS:
        keep *= 1. - _guard((height, width), box)
    keep *= np.clip((CONTACT_ROW - yy) / 10. + .5, 0., 1.)
    return (gauss(*CHEST) + gauss(*HIP) * HIP_FOLLOW) * keep


@lru_cache(maxsize=2)
def breath_maps(width, height):
    grid = np.mgrid[0:height, 0:width].astype(np.float32)
    return np.float32(grid[1]), grid[0]



def mix_frames(first, last, weight):
    """Weighted premultiplied sum, without source-over alpha/brightness pumping."""
    if first is None or weight >= 1:
        return last
    if weight <= 0:
        return first
    output = QImage(last.size(), QImage.Format.Format_RGBA32FPx4_Premultiplied)
    output.fill(0)
    painter = QPainter(output)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
    for source, opacity in ((first, 1-weight), (last, weight)):
        layer = source.toImage().convertToFormat(output.format())
        mask = QPainter(layer)
        mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        color = QColor(0, 0, 0)
        color.setAlphaF(opacity)
        mask.fillRect(layer.rect(), color)
        mask.end()
        painter.drawImage(0, 0, layer)
    painter.end()
    return QPixmap.fromImage(output)


def sleep_time(at=None):
    hour = (at or datetime.now()).hour
    return hour < 7 or hour == 13


class SleepCycle:
    def __init__(self):
        self.phase = 'awake'
        self.started = 0.
        self.awake_until = 0.
        self.reason = ''
        self.frames = {}
        self.preload_cursor = 0
        self.breath_started = 0.
        self._breath_key = None
        self._breath_frame = None
        self.wake_source = None
        self.last_frame = None
        self.interrupted_settle = None
        self.wake_seconds = WAKE_SECONDS
        self.site_attempted = False
        self.site_deadline = 0.
        self.rest_site = None
        self.rest_geometry = None
        self.site_mask = False
        self.site_probe_at = 0.
        self.action_started = None
        self.action_generation = None
        # Decode one small frame per idle tick. Prioritize sequence endpoints
        # so a cold launch does not batch-decode an animation on pointer input.
        self.preload_keys = [('settle', 0), ('wake', 0), 0]
        self.preload_keys += [('settle', i) for i in range(1, MANIFEST['settle']['count'])]
        self.preload_keys += [('wake', i) for i in range(1, MANIFEST['wake']['count'])]
        self.preload_keys += list(range(1, 96))

    @property
    def active(self):
        return self.phase in ('settling', 'asleep')

    @property
    def transitioning(self):
        return self.active or self.phase == 'waking'

    def wake(self, pet, reason='点击', now=None):
        now = time.monotonic() if now is None else now
        was = self.active
        self.awake_until = now+120
        self.site_attempted = False
        self.site_deadline = 0.
        self.clear_rest_site(pet)
        self.reason = reason
        if was:
            # Reverse an interrupted head-settle from its present pose, rather
            # than flashing fully shut eyes before beginning the wake sequence.
            self.interrupted_settle = (min(1., max(0., (now-self.started)/SETTLE_SECONDS))
                                       if self.phase == 'settling' else None)
            self.wake_seconds = (.6*self.interrupted_settle+.4
                                 if self.interrupted_settle is not None else WAKE_SECONDS)
            self.wake_source = self.last_frame
            self.phase, self.started = 'waking', now
            if 'sleep-wake' in catalog():
                self.play_sleep_action(pet, 'sleep-wake', now)
            else:
                self.stop_sleep_action(pet)
                pet.state.action_player.stop()
            pet.state.ambient.current = None
            pet.state.ambient.next_at = now+5
            pet.renderer.pointer_hold_image = None
            pet.state_changed.emit()

    def play_sleep_action(self, pet, action_id, now, *, loop=False):
        """Use the authored catalog sleep clips for real scheduled transitions."""
        if action_id not in catalog():
            return False
        player = pet.state.action_player
        player.play(action_id, now=now, loop=loop)
        self.action_started = player.started
        self.action_generation = player.generation
        return True

    def stop_sleep_action(self, pet):
        player = pet.state.action_player
        if (self.action_started is not None and player.started == self.action_started
                and player.generation == self.action_generation):
            player.stop()
        self.action_started = self.action_generation = None

    def tick(self, pet, now):
        s = pet.state
        if self.rest_site and now >= self.site_probe_at:
            self.site_probe_at = now+1
            icons = s.icon_sleep
            current = next((i for i in icons.icons if i['id'] == self.rest_site['id']),None) if icons else None
            if (not current or current['rect'] != self.rest_site['rect'] or icons.error
                    or self.rest_geometry != (pet.screen(),pet.width(),pet.height(),pet.pos())
                    or not s.patrol.route_exposed((pet.x(),pet.y()),pet.screen())):
                self.clear_rest_site(pet)
            elif now-icons.scanned_at > 3:
                icons.refresh()
        patrol = s.patrol
        owns_action = bool(patrol and patrol.active is True and
                           s.action_player.action and
                           s.action_player.generation == patrol.owned_generation)
        owns_icon = bool(patrol and patrol.active is True and patrol.kind == 'lean'
                         and s.icon_sleep and s.icon_sleep.target is patrol.target)
        owns_music = bool(s.music and isinstance(s.music.active,str) and s.music.active
                          and s.action_player.action
                          and s.action_player.started == s.music.owned_start
                          and s.action_player.generation == s.music.owned_generation)
        recovery = getattr(pet,'dance_recovery',None)
        owns_recovery = bool(recovery and recovery.owned_start is not None
                             and s.action_player.action
                             and s.action_player.started == recovery.owned_start
                             and s.action_player.generation == recovery.owned_generation)
        attached = (bool(s.edge_attachment and s.edge_attachment.active)
                    or bool(s.icon_sleep and s.icon_sleep.target and not owns_icon))
        busy = (pet.drag_origin is not None or s.physics.active or pet.presence.active
                or attached
                or bool(getattr(pet.controller, 'quick_pending', None))
                or bool(pet.bubble.parts and pet.bubble.kind != 'ambient'))
        if busy and self.awake_until:
            self.awake_until = max(self.awake_until, now+120)
        if self.phase == 'waking' and now-self.started >= self.wake_seconds:
            self.stop_sleep_action(pet)
            self.phase = 'awake'
            self.wake_source = None
            self.interrupted_settle = None
            s.ambient.next_at = max(s.ambient.next_at, now+5)
            pet.state_changed.emit()
        if self.active and not sleep_time():
            self.wake(pet, '睡眠时段结束', now)
        if not sleep_time():
            self.site_attempted = False
            if patrol and patrol.kind == 'sleep_site':
                patrol.suspend(now, '睡眠时段结束，取消休息路线')
        if (not self.active and self.phase != 'waking' and sleep_time()
                and not (patrol and getattr(patrol, 'exploring', False) is True)
                and now >= self.awake_until and not busy and pet.isVisible()
                and not (s.action_player.action and not s.ambient.current
                         and not owns_action and not owns_music and not owns_recovery)
                and not pet.preferences.paused):
            if not self.site_attempted:
                if owns_music:
                    s.music.cancel(now)
                if owns_recovery:
                    s.action_player.stop()
                    recovery.owned_start = recovery.watched = None
                self.site_attempted = True
                self.site_deadline = now+10
                if patrol and patrol.begin_sleep_site(now) is True:
                    return
            if (patrol and patrol.kind == 'sleep_site' and patrol.active is True
                    and now < self.site_deadline):
                return
            if s.patrol:
                s.patrol.suspend(now, '进入正式睡眠')
            if s.music:
                s.music.cancel()
            s.travel_target = s.travel_position = s.roll_path = None
            s.walking = False
            s.gait_until = 0
            s.ambient.current = None
            s.action_player.stop()
            pet.bubble.clear()
            self.phase, self.started = 'settling', now
            self.last_frame = self.wake_source = None
            self.interrupted_settle = None
            if not self.play_sleep_action(pet, 'sleep-enter', now):
                self.action_started = self.action_generation = None
            pet.state_changed.emit()
        if self.phase == 'settling' and now-self.started >= SETTLE_SECONDS:
            # Anchor breath phase to the end of settling, not the last tick.
            self.breath_started = self.started+SETTLE_SECONDS
            self.phase = 'asleep'
            if not self.play_sleep_action(pet, 'sleep', now, loop=True):
                self.action_started = self.action_generation = None
            pet.state_changed.emit()

    def snapshot(self):
        return dict(phase=self.phase, sleeping=self.active, scheduled=sleep_time(),
                    resume_in=max(0, round(self.awake_until-time.monotonic())),
                    schedule='00:00–07:00 · 13:00–14:00', wake_reason=self.reason)

    def set_rest_site(self, pet, target, icons):
        """Optional icon occlusion; never attach a second position controller."""
        self.clear_rest_site(pet)
        if target is None:
            return
        image = icons.cache_images.get(target['id'])
        if image is None:
            return
        from icon_sleep import logical_rect, alpha_region
        from PySide6.QtGui import QRegion
        x,y,w,h = logical_rect(target['rect'])[0]
        glyph = alpha_region(image.scaled(max(1,round(w)),max(1,round(h))))
        if glyph.isEmpty():
            return
        self.rest_site = dict(id=target['id'],rect=dict(target['rect']))
        self.rest_geometry = (pet.screen(),pet.width(),pet.height(),pet.pos())
        pet.masker.set('sleep_site',QRegion(pet.rect()).subtracted(glyph.translated(round(x-pet.x()),round(y-pet.y()))))
        self.site_mask = True

    def clear_rest_site(self, pet):
        if self.site_mask:
            pet.masker.clear('sleep_site')
        self.site_mask = False
        self.rest_site = self.rest_geometry = None

    def interrupt_for_drag(self):
        # Pointer/throw physics own the pose immediately after the gesture
        # crosses the drag threshold; a pending wake must not suspend them.
        self.phase = 'awake'
        self.action_started = self.action_generation = None
        self.wake_source = self.last_frame = None
        self.interrupted_settle = None

    def frame(self, index):
        if index not in self.frames:
            path = (ASSETS/'transitions'/f'{index[0]}-{index[1]:03}.png'
                    if isinstance(index, tuple) else ASSETS/f'{index:02}.png')
            self.frames[index] = QPixmap(str(path))
        return self.frames[index]

    def preload(self):
        if self.preload_cursor < len(self.preload_keys):
            self.frame(self.preload_keys[self.preload_cursor])
            self.preload_cursor += 1

    def sequence_frame(self, clip, seconds):
        spec = MANIFEST[clip]
        index = min(spec['count']-1, max(0, round(seconds*MANIFEST['fps'])))
        return self.frame((clip, index))

    def transition_frame(self, clip, elapsed):
        """Stretch the baked sequence across its approved playback time."""
        spec = MANIFEST[clip]
        playback = SETTLE_SECONDS if clip == 'settle' else max(
            .001, WAKE_SECONDS-WAKE_HOLD_SECONDS)
        return self.sequence_frame(clip, min(1., elapsed/playback)*spec['seconds'])

    def sample(self, now):
        elapsed = max(0., now-self.started)
        if self.phase == 'settling':
            return self.transition_frame('settle', elapsed)
        if self.phase == 'waking':
            if self.interrupted_settle is not None:
                reverse_seconds = .6*self.interrupted_settle
                if elapsed < reverse_seconds:
                    source_time = (1-elapsed/reverse_seconds)*self.interrupted_settle*MANIFEST['settle']['seconds']
                    frame = self.sequence_frame('settle', source_time)
                else:
                    frame = self.sequence_frame('wake', .6+elapsed-reverse_seconds)
            else:
                frame = self.transition_frame('wake', elapsed)
            # Carry the last rendered breathing/settling pose into wake-up.
            # Only matching silhouettes are mixed, for the initial 120 ms.
            progress = min(1., elapsed/.12)
            weight = progress*progress*(3-2*progress)
            return mix_frames(self.wake_source, frame, weight)
        return self.frame(int(max(0., now-self.breath_started)*20) % 96)

    def breath_offset(self, now):
        """Signed chest displacement in source pixels for this instant.

        Settling exhales into sleep: the half-cycle that ends the head-lower is
        the descending zero of the clock the asleep loop starts from, so the
        handover never reverses direction. SETTLE_SECONDS is half BREATH_SECONDS
        for exactly that reason.
        """
        if self.phase == 'settling':
            elapsed = max(0., now-self.started)
            if elapsed > SETTLE_SECONDS:
                return 0.
            t = min(1., elapsed/SETTLE_SECONDS)
            ramp = .6+.4*t*t*(3-2*t)
            return -BREATH_AMPLITUDE*ramp*math.sin(math.tau*elapsed/BREATH_SECONDS)
        if self.phase != 'asleep':
            return 0.
        return BREATH_AMPLITUDE*math.sin(math.tau*(now-self.breath_started)/BREATH_SECONDS)

    def warped_frame(self, frame, now):
        """The breathing pose as a frame, so waking starts from what is visible."""
        # Half-pixel buckets: at this amplitude a whole-pixel step would land
        # roughly every fifth of a second and read as a tick, not a breath.
        offset = round(self.breath_offset(now)*2)/2
        if not offset or frame is None or frame.isNull() \
                or (frame.width(), frame.height()) != SIZE:
            return frame
        key = (frame.cacheKey(), offset)
        if key == self._breath_key:
            return self._breath_frame
        image = frame.toImage().convertToFormat(QImage.Format.Format_RGBA8888_Premultiplied)
        width, height = image.width(), image.height()
        rgba = np.frombuffer(image.constBits(), np.uint8)
        rgba = rgba.reshape(height, image.bytesPerLine()//4, 4)[:, :width]
        map_x, map_y = breath_maps(width, height)
        shifted = np.clip(map_y+breath_field(width, height)*offset, 0, height-1)
        warped = cv2.remap(np.ascontiguousarray(rgba), map_x, np.ascontiguousarray(shifted),
                           cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
        self._breath_key = key
        self._breath_frame = QPixmap.fromImage(QImage(
            warped.data, width, height, width*4,
            QImage.Format.Format_RGBA8888_Premultiplied).copy())
        return self._breath_frame

    def paint(self, painter, now):
        elapsed = max(0., now-self.started)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, True)
        frame = self.sample(now)
        if frame.isNull():
            return False
        # The drawn pose is the one a click has to continue from, breath included.
        self.last_frame = self.warped_frame(frame, now)
        painter.drawPixmap(QRectF(5, 20, 170, 164), self.last_frame,
                           QRectF(self.last_frame.rect()))
        if self.phase != 'waking':
            # Letters appear after the eyelids have closed, not while sleepy.
            settle = min(1., max(0., (elapsed-1.1)/.5)) if self.phase == 'settling' else 1.
            letter_time = now-self.started
            painter.save()
            painter.setFont(QFont('Comic Sans MS', 12, QFont.Weight.Bold))
            for j in range(3):
                p = (letter_time/4.8+j/3) % 1
                alpha = round(210*max(0, min(1, p/.18, (1-p)/.25))*settle)
                painter.setPen(QColor(114, 141, 199, alpha))
                painter.drawText(QRectF(124+28*p, 37-15*p, 20, 24), 'z')
            painter.restore()
        return True
