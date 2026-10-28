"""Scheduled continuous sleep, independent of random idle clips."""
from datetime import datetime
from pathlib import Path
import json
import time
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPixmap

ASSETS = Path(__file__).resolve().parent/'assets'/'sleep'
MANIFEST = json.loads((ASSETS/'transitions/manifest.json').read_text(encoding='utf-8'))
PLAYBACK = MANIFEST.get('playback', {})
SETTLE_SECONDS = PLAYBACK.get('settle', MANIFEST['settle']['seconds'])
WAKE_SECONDS = PLAYBACK.get('wake', MANIFEST['wake']['seconds'])
WAKE_HOLD_SECONDS = PLAYBACK.get('wake_hold', 0.)


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
            pet.state.action_player.stop()
            pet.state.ambient.current = None
            pet.state.ambient.next_at = now+5
            pet.renderer.pointer_hold_image = None
            pet.state_changed.emit()

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
            pet.state_changed.emit()
        if self.phase == 'settling' and now-self.started >= SETTLE_SECONDS:
            # Anchor breath phase to the end of settling, not the last tick.
            self.breath_started = self.started+SETTLE_SECONDS
            self.phase = 'asleep'
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

    def paint(self, painter, now):
        elapsed = max(0., now-self.started)
        painter.setRenderHint(painter.RenderHint.SmoothPixmapTransform, True)
        frame = self.sample(now)
        if frame.isNull():
            return False
        self.last_frame = frame
        painter.save()
        painter.drawPixmap(QRectF(5, 20, 170, 164), frame, QRectF(frame.rect()))
        if self.phase != 'waking':
            # Letters appear after the eyelids have closed, not while sleepy.
            settle = min(1., max(0., (elapsed-1.1)/.5)) if self.phase == 'settling' else 1.
            letter_time = now-self.started
            painter.setFont(QFont('Comic Sans MS', 12, QFont.Weight.Bold))
            for j in range(3):
                p = (letter_time/4.8+j/3) % 1
                alpha = round(210*max(0, min(1, p/.18, (1-p)/.25))*settle)
                painter.setPen(QColor(114, 141, 199, alpha))
                painter.drawText(QRectF(124+28*p, 37-15*p, 20, 24), 'z')
        painter.restore()
        return True
