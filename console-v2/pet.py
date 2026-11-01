"""A small Windows-friendly desktop cat. Run with Python 3.10+."""
import ctypes
import math
import random
import time
from ctypes import wintypes as _wintypes
from copy import copy
from pathlib import Path
from functools import lru_cache

from idle_animation import IdleAnimation, motion_phase
from action_player import ActionPlayer, catalog
from action_life_motion import ActionLifeMotion
from action_inbetweens import prefetch, sample_pose
from frame_alignment import offset_for as action_frame_offset
from idle_actions import IdleActions
from idle_states import STATES, posture_for
from click_reaction import ClickReaction
from pet_physics import PetPhysics, PointerVelocity
from pet_presence import Presence
from daily_routine import DailyRoutine
from pet_sleep import SleepCycle, sleep_time
from pet_mask import WindowMask
from locomotion import frame as motion_frame, step_towards, metadata as motion_metadata, gait_advance, walk_stride, walking_name, vertical_walk
from walk_rig import paint as paint_walk, rig as walk_rig
from vertical_walk_rig import paint as paint_vertical, frame_rect as vertical_frame_rect, rig as vertical_rig

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QCursor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from settings_model import Preferences


FRAME_INTERVAL_MS = 16


class _NativeMessage(ctypes.Structure):
    _fields_ = [('hwnd', _wintypes.HWND), ('message', _wintypes.UINT),
                ('wParam', _wintypes.WPARAM), ('lParam', _wintypes.LPARAM),
                ('time', _wintypes.DWORD), ('pt', _wintypes.POINT)]


CLICK_REACTIONS = ('affection', 'shy', 'smile', 'clicked')


class PetState:
    """只保存宠物状态，不负责窗口、绘图或用户输入。"""

    def __init__(self):
        self.paused = False
        self.direction = 1
        self.walking = False
        self.position_x = 0.0
        self.jump_started = None
        self.message_until = 0.0
        self.started = time.monotonic()
        self.last_tick = self.started
        self.idle = IdleAnimation(now=self.started)
        self.action_player = ActionPlayer()
        self.ambient = IdleActions()
        self.routine = DailyRoutine()
        self.ambient.set_period(self.routine.period)
        self.ambient.defer(self.started)
        self.ambient.next_at=self.started+random.uniform(5,8)
        self.icon_sleep = None
        self.edge_attachment = None
        self.gait_clock = 0.
        self.gait_direction = None
        self.gait_name = None
        self.gait_target = None
        self.gait_distance = 0.
        self.gait_until = 0.
        self.gait_energy = 0.
        self.gait_energy_at = 0.
        self.gait_vector = (1.,0.)
        self.gait_render_offset = (0.,0.)
        self.gait_window_position = None
        self.travel_target = None
        self.travel_position = None
        self.drag_feedback = None
        self.click_reaction = ClickReaction()
        self.physics = PetPhysics()
        self.pointer_velocity = PointerVelocity()
        self.patrol = None
        self.music = None
        self.roll_path = None
        self.dance_depth_scale = 1.
        self.sleep = SleepCycle()
        self.status_performance = None
        self.hover_direction = 0.
        self.hover_at = None
        self.hover_inside = False

    def hover_transform(self, now):
        if self.hover_at is None:
            return 0., 0.
        if self.hover_inside:
            weight = min(1., max(0., (now-self.hover_at)/.25))
        else:
            weight = max(0., 1.-(now-self.hover_at)/.35)
        if weight <= 0:
            return 0., 0.
        return self.hover_direction*3.2*weight, self.hover_direction*1.15*weight

    def current_gait_energy(self, now):
        """Stride strength: ramps in while moving, fades out after stopping."""
        # A short grace keeps 60Hz draws at full strength between movement
        # ticks; the fade then lands exactly at the walk hold's end.
        return max(0., self.gait_energy-max(0., now-self.gait_energy_at-.02)/.18)

    def gait_settled(self, now):
        return now-self.gait_energy_at >= .32


class PetAnimator:
    """负责定时更新移动和跳跃状态。"""

    def __init__(self, pet):
        self.pet = pet
        self.timer = QTimer(pet)
        self.timer.timeout.connect(self.tick)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.start(FRAME_INTERVAL_MS)
        self.ambient_blocked = False

    def tick(self):
        state = self.pet.state
        now = time.monotonic()
        if now-state.last_tick > 2 and state.patrol and state.patrol.active:
            state.patrol.suspend(now, '系统恢复，丢弃旧路线')
        dt = min(now - state.last_tick, 0.1)
        state.last_tick = now
        state.idle.update(now)
        self.pet.dance_recovery.tick(now)
        state.action_player.frame(now)
        # Decode optional sleep assets only while stationary, off the walking path.
        if (self.pet.drag_origin is None and not state.physics.active
                and not state.walking and state.travel_target is None
                and now >= state.gait_until and not self.pet.presence.active):
            state.sleep.preload()
        state.sleep.tick(self.pet, now)
        if state.music:
            state.music.tick(now)
        if state.patrol:
            state.patrol.tick(now, dt)
        focus = getattr(self.pet, 'focus', None)
        if focus:
            focus.tick(now)
        perch = getattr(self.pet, 'window_perch', None)
        if perch:
            perch.tick(now)
        awareness = getattr(self.pet, 'awareness', None)
        if awareness:
            awareness.tick(now)
        self.update_ambient(now)
        self.pet.dance_stage.advance(now)

        previous = self.pet.status_text()
        if state.sleep.transitioning:
            state.walking = False
        elif self.pet.presence.active:
            state.walking = False
        elif self.pet.dance_stage.active:
            state.walking = False
        elif state.physics.active:
            self.pet.advance_physics(dt)
        elif self.advance_roll(now):
            pass
        elif state.travel_target is not None:
            if self.pet.drag_origin is None and self.pet.isVisible():
                if self.pet.advance_to(state.travel_target,dt):
                    state.travel_target=None
                    self.pet.position_settled.emit()
        else:
            state.walking = False

        if state.jump_started is not None and now - state.jump_started >= 0.65:
            state.jump_started = None
        self.pet.update()
        if previous != self.pet.status_text():
            self.pet.state_changed.emit()

    def advance_roll(self, now):
        state = self.pet.state
        player = state.action_player
        action = player.action
        if action and action.get('lazy_roll'):
            if self.pet.drag_origin is not None or not self.pet.isVisible():
                state.roll_path = None
                return False
            if not state.roll_path or state.roll_path[0] != player.started:
                area = self.pet.screen_area()
                top = area.top()
                bottom = max(top, area.bottom()-self.pet.height()+1)
                origin = max(top, min(bottom, float(self.pet.y())))
                # The head-to-feet axis is horizontal in the approved sprites.
                # Rolling across that axis means toward = up, away = down.
                from action_player import ROLL_DIRECTION
                direction = ROLL_DIRECTION[action['id']]
                room = bottom-origin if direction > 0 else origin-top
                distance = min(150.*self.pet.height()/180, room)
                target = origin+direction*distance
                patrol = state.patrol
                if patrol and patrol.active and getattr(patrol, 'roll_origin', None):
                    _, py, distance = patrol.roll_origin
                    origin, target = float(py), max(top, min(bottom, py+direction*abs(distance)))
                total = sum(player.action['durations'])/1000/player.speed
                state.roll_path = (player.started, float(self.pet.x()), origin, target, player.started+total)
            started, fixed_x, origin, target, _ = state.roll_path
            progress = player.roll_progress(now)
            if progress is not None:
                y = origin+(target-origin)*progress
                state.position_x = fixed_x
                self.pet.move(round(fixed_x), round(y))
                state.walking = False
                state.gait_until = 0
                return True
        elif state.roll_path:
            started, fixed_x, _, target, end_at = state.roll_path
            if player.action is None and player.started == started and now >= end_at:
                state.position_x = fixed_x
                self.pet.move(round(fixed_x), round(target))
            state.roll_path = None
        return False

    def update_ambient(self, now):
        pet = self.pet
        state = pet.state
        if state.sleep.transitioning:
            return
        ambient = state.ambient
        player = state.action_player
        changed = state.routine.update()
        if changed or ambient.period_key != state.routine.period['key']:
            ambient.set_period(state.routine.period)
            state.walking = False
            pet.state_changed.emit()
        else:
            ambient.set_period(state.routine.period)
        # A sleep clip breathes for a while instead of standing up every few
        # seconds. Manual input clears ambient.current and always takes priority.
        if ambient.current and player.loop and now-ambient.current[1] >= ambient.current[3]:
            player.stop()
        blocked = (not pet.isVisible() or pet.drag_origin is not None
                   or pet.preferences.paused or pet.preferences.quiet
                   or bool(getattr(pet.controller, 'quick_pending', None))
                   or bool(pet.bubble.parts and pet.bubble.kind != 'ambient')
                   or state.physics.active
                   or pet.presence.active
                   or bool(state.patrol and (state.patrol.active or state.patrol.exploring))
                   or bool(state.music and state.music.active)
                   or state.travel_target is not None
                   or not state.gait_settled(now)
                   or bool(state.icon_sleep and state.icon_sleep.target)
                   or bool(state.edge_attachment and state.edge_attachment.active))
        if ambient.current:
            key, started, origin, duration = ambient.current
            if blocked or not player.action or player.action['id'] != key or player.started != started:
                completed = not blocked and player.action is None and now-started >= duration
                if blocked and player.action and player.started == started:
                    player.stop()
                ambient.current = None
                ambient.defer(now, pet.preferences.activity)
                posture = catalog().get(key, {}).get('end_posture')
                if completed and posture in ('sit', 'prone'):
                    # Already seated after rolling: skip the lowering section,
                    # dwell in a living seated state, then play its rise once.
                    followup = 'prone-rest' if posture == 'prone' else 'sit-neat'
                    seated = catalog().get(followup)
                    if seated:
                        seated_start = now-sum(seated['durations'][:3])/1000
                        ambient.play(player, followup, seated_start)
                        ambient.current = (followup, seated_start, float(pet.x()),
                                           sum(player.action['durations'])/1000)
                        return
        if blocked:
            if not self.ambient_blocked:
                ambient.defer(now, pet.preferences.activity)
            self.ambient_blocked = True
            return
        if self.ambient_blocked:
            # Resume gently after an interaction, without waiting another full
            # ambient interval or letting patrol repeatedly win the free slot.
            ambient.next_at = now + random.uniform(3, 6)
        self.ambient_blocked = False
        if player.action is not None:
            return
        if now < ambient.next_at:
            return
        available = catalog()
        if state.patrol:
            available = {key: action for key, action in available.items() if key != 'eat'}
        key = ambient.choose(available)
        ambient.defer(now, pet.preferences.activity)
        if key is None:
            return
        duration = ambient.play(player, key, now)
        ambient.current = (key, now, float(pet.x()), duration)
        state.walking = False
        state.gait_until = 0
        pet.state_changed.emit()

    def jump(self):
        if not self.pet.isVisible():
            return
        self.pet.wake_icon_sleep()
        now = time.monotonic()
        self.pet.state.jump_started = now
        self.pet.state.message_until = (
            now + 1.5 if self.pet.preferences.greeting and not self.pet.preferences.quiet else 0)
        self.pet.state_changed.emit()


class PetRenderer:
    """Cached transparent artwork; animation state is updated by PetAnimator."""

    @staticmethod
    @lru_cache(maxsize=1)
    def load_atlases():
        folder = Path(__file__).resolve().parent / 'assets' / 'living-idle'
        atlases = {name: QPixmap(str(folder / f'{name}.png'))
                   for name in ('open', 'half', 'closed')}
        if any(frame.isNull() or frame.width() != 2048 or frame.height() != 2048
               for frame in atlases.values()):
            raise RuntimeError(f'宠物素材缺失，请保留完整 assets 文件夹：{folder}')
        return atlases

    def __init__(self):
        self.atlases = self.load_atlases()
        self.interaction_atlases()
        walk_rig()
        vertical_rig()
        self.action_motion = ActionLifeMotion()
        self.last_pose = None
        self.last_image = None
        self.transition_image = None
        self.transition_started = 0
        self.transition_duration = .055
        self.pointer_hold_image = None
        self.last_display_image = None

    def draw(self, painter, state):
        # Dragging needs immediate cursor feedback, without a stale pose overlay.
        if state.drag_feedback is not None:
            self.pointer_hold_image = None
            self.last_pose = None
            self.last_image = None
            self.transition_image = None
            self.draw_pose(painter, state)
            return
        if self.pointer_hold_image is not None:
            painter.drawImage(0, 0, self.pointer_hold_image)
            return
        now = time.monotonic()
        frame = state.action_player.frame(now)
        action = state.action_player.action
        gait_visible = now < state.gait_until or state.current_gait_energy(now) > 0
        pose = ('sleep',) if state.sleep.active or state.sleep.phase == 'waking' else ('physics',) if state.physics.active else ('action', action['id'], None if action['id']=='music-waltz' else state.action_player.started) if action else (
            ('walk', state.gait_name or state.direction) if gait_visible else ('idle',))
        if action and action.get('click_expression') and pose[0] == 'action':
            pose = (*pose, 'click-expression')
        # Keep source detail through the intermediate canvases. Device pixel
        # ratio preserves the existing 180x190 logical geometry and pivots.
        image = QImage(360, 380, QImage.Format.Format_RGBA32FPx4_Premultiplied)
        image.setDevicePixelRatio(2.)
        image.fill(Qt.GlobalColor.transparent)
        layer = QPainter(image)
        self.draw_pose(layer, state)
        layer.end()
        raw_image = image
        if state.physics.active:
            self.transition_image = None
        if self.last_pose is not None and pose != self.last_pose and not state.physics.active:
            from motion_transition import handover_duration
            self.transition_duration = handover_duration(self.last_pose,pose,self.last_image,image)
            if (pose[-1] == 'click-expression' or self.last_pose[-1] == 'click-expression') and pose[0] in ('idle','action'):
                self.transition_duration = .18
            self.transition_image = self.last_image if self.transition_duration else None
            self.transition_started = now
        progress = min(1., max(0., (now-self.transition_started)/self.transition_duration)) if self.transition_duration else 1.
        if self.transition_image is not None and progress < 1:
            # Smoothstep eases both ends; weighted addition preserves alpha at
            # overlapping translucent edges instead of flashing brighter.
            weight = progress*progress*(3-2*progress)
            mixed = QImage(image.size(), image.format())
            mixed.setDevicePixelRatio(image.devicePixelRatio())
            mixed.fill(Qt.GlobalColor.transparent)
            for source, opacity in ((self.transition_image, 1-weight), (image, weight)):
                weighted = source.copy()
                mask = QPainter(weighted)
                mask.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
                color = QColor(0, 0, 0)
                color.setAlphaF(opacity)
                mask.fillRect(weighted.rect(), color)
                mask.end()
                blend = QPainter(mixed)
                blend.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
                blend.drawImage(0, 0, weighted)
                blend.end()
            image = mixed
        else:
            self.transition_image = None
        self.last_pose = pose
        # Never recycle an already mixed image: repeated input must not leave
        # an exponentially decaying trail of earlier poses.
        self.last_image = raw_image
        displayed = QImage(image.size(), image.format())
        displayed.setDevicePixelRatio(image.devicePixelRatio())
        displayed.fill(Qt.GlobalColor.transparent)
        display = QPainter(displayed)
        dx, dy, angle, scale_x, scale_y, shear = 0., 0., 0., 1., 1., 0.
        if state.music:
            mx, my, tilt = state.music.transform(now)
            dx += mx
            dy += my
            angle += tilt
        if not state.sleep.active and not state.sleep.transitioning and not state.physics.active:
            hx, htilt = state.hover_transform(now)
            dx += hx
            angle += htilt
        if state.physics.active:
            lean, sx, sy = state.physics.transform()
            angle += lean
            scale_x *= sx
            scale_y *= sy
        display.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        pivot = 105 if state.physics.active and state.physics.flying else 178
        display.translate(90+dx, pivot+dy)
        display.rotate(angle)
        display.shear(shear, 0)
        display.scale(scale_x, scale_y)
        display.translate(-90, -pivot)
        display.drawImage(0, 0, image)
        display.end()
        self.last_display_image = displayed
        painter.drawImage(0, 0, displayed)

    def motion_image(self, elapsed, eye_frame):
        first, second, fraction = motion_phase(elapsed)
        expression = 'closed' if eye_frame == 10 else 'half' if eye_frame == 4 else 'open'
        atlas = self.atlases[expression]
        image = QImage(256, 256, QImage.Format.Format_RGBA32FPx4_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        # Qt Plus + painter opacity does NOT compute a weighted sum: it also
        # attenuates the destination, pumping alpha and brightness every cell.
        # Weight sources with high-precision DestinationIn masks on float
        # surfaces, then add at full opacity. Avoid QPainter.setOpacity here:
        # its 8-bit fast path also loses alpha even on float destinations.
        for index, weight in ((first, 1-fraction), (second, fraction)):
            layer = QImage(256, 256, QImage.Format.Format_RGBA32FPx4_Premultiplied)
            layer.fill(Qt.GlobalColor.transparent)
            source = QPainter(layer)
            source.drawPixmap(QRectF(0, 0, 256, 256), atlas,
                           QRectF((index % 8)*256, (index // 8)*256, 256, 256))
            source.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
            mask = QColor(0, 0, 0)
            mask.setAlphaF(weight)
            source.fillRect(0, 0, 256, 256, mask)
            source.end()
            mix = QPainter(image)
            mix.setCompositionMode(QPainter.CompositionMode.CompositionMode_Plus)
            mix.drawImage(0, 0, layer)
            mix.end()
        return QPixmap.fromImage(image)

    def apply_click_reaction(self, painter, state, reaction):
        # Warping the sprite at its source keeps one resampling. Applying the
        # same matrix to the composited canvas softened every click.
        dx, dy, angle, scale_x, scale_y, shear = reaction
        if reaction == (0., 0., 0., 1., 1., 0.):
            return
        pivot = 105 if state.physics.active and state.physics.flying else 178
        painter.translate(90+dx, pivot+dy)
        painter.rotate(angle)
        painter.shear(shear, 0)
        painter.scale(scale_x, scale_y)
        painter.translate(-90, -pivot)

    def draw_pose(self, painter, state, now=None):
        now = time.monotonic() if now is None else now
        # Actions composite their breathing warp at 160px. Scaling that raster
        # up for the jelly (click) feedback re-blurs it, so keep the warp at
        # source resolution for as long as a non-identity transform is applied.
        reaction = state.click_reaction.transform(now)
        warp_size = 160 if reaction == (0., 0., 0., 1., 1., 0.) else 256
        if (state.sleep.active or state.sleep.phase == 'waking') and state.drag_feedback is None:
            painter.save()
            self.apply_click_reaction(painter, state, reaction)
            painted = state.sleep.paint(painter, now)
            painter.restore()
            if painted:
                return
        elapsed = now - state.started
        jump = 0 if state.jump_started is None else 36 * math.sin(
            math.pi * max(0, min(1, (now - state.jump_started) / .65)))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if state.drag_feedback is not None:
            state.drag_feedback.paint(painter, now)
            return
        physics_frame = state.physics.animation_frame()
        if physics_frame is not None:
            action_id, frame = physics_frame
            atlas = self.action_atlas(action_id)
            painter.save()
            self.apply_click_reaction(painter, state, reaction)
            painter.drawPixmap(QRectF(10, 25, 160, 160), atlas,
                               QRectF((frame % 4)*256, (frame // 4)*256, 256, 256))
            painter.restore()
            return
        frame = state.action_player.frame(now)
        if frame is not None:
            action = state.action_player.action
            if not action.get('authored_motion'):
                prefetch(state.action_player.upcoming_pairs(now))
            if action.get('pixel_art'):
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            before, after, progress = state.action_player.motion_sample(now)
            visual_id, visual_frame = before
            visual_action = catalog()[visual_id]
            if visual_id == 'music-waltz':
                from music_dance_asset import frame as dance_frame
                sampled = dance_frame(visual_frame)
                if sampled is None:
                    # Retain a visible idle while the very first page is decoded.
                    painter.drawPixmap(QRectF(10,25,160,160),self.motion_image(elapsed,state.idle.frame),QRectF(0,0,256,256))
                    return
                atlas, source = sampled
            else:
                atlas = self.action_atlas(visual_id)
                source = QRect((visual_frame % visual_action['columns'])*256,
                               (visual_frame // visual_action['columns'])*256, 256, 256)
            interpolated = None if action.get('authored_motion') else sample_pose(before, after, progress)
            if interpolated is not None:
                atlas, source = interpolated
            # A late decoder leaves the authored source pose on screen. Its
            # anchor must stay at that source too, rather than sliding toward
            # an unseen destination pose and snapping back on the next tick.
            offset_x, offset_y = ((0., 0.) if action.get('authored_motion') else action_frame_offset(
                before, after, progress if interpolated is not None else 0.))
            painter.save()
            self.apply_click_reaction(painter, state, reaction)
            painter.translate(offset_x*160/256, offset_y*160/256)
            # The warp already carries the authored in-between motion; a remap
            # on top would cost another 3.5ms and smear the interpolated edges.
            # A long hold reads as an idle only if it keeps breathing. Clips
            # flagged `idle_life` opt into the secondary motion that authored
            # actions otherwise skip; the warp anchors at the feet.
            life = action.get('idle_life') or {}
            if isinstance(life, (int, float)):
                life = {'scale': float(life)}
            lived = None if (interpolated is not None or (
                action.get('authored_motion') and not life)) else self.action_motion.render(
                    atlas, source, visual_id, elapsed, warp_size, **life)
            target = QRectF(10, 25, 160, 160)
            if action.get('spatial_dance') or action.get('grounded_pose'):
                depth = state.dance_depth_scale if action.get('spatial_dance') else 1.
                painter.translate(90, 181.875)
                painter.scale(depth, depth)
                painter.translate(-90, -181.875)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(45, 73, 98, 36))
                painter.drawEllipse(QRectF(57, 179.5, 66, 4))
                target = QRectF(10, 181.875-160*action['baseline'], 160, 160)
            if lived is not None:
                painter.drawImage(target, lived)
            elif isinstance(atlas, QImage):
                painter.drawImage(target, atlas, QRectF(source))
            else:
                painter.drawPixmap(target, atlas, QRectF(source))
            painter.restore()
            return
        gait_energy = max(0., min(1., state.current_gait_energy(now)))
        if now < state.gait_until or gait_energy > 0:
            name=state.gait_name or ('walk-right' if state.direction>0 else 'walk-left')
            painter.save()
            painter.translate(*state.gait_render_offset)
            self.apply_click_reaction(painter, state, reaction)
            if vertical_walk(name):
                paint_vertical(painter,vertical_frame_rect(name),name,state.gait_clock,
                               energy=gait_energy)
            else:
                target = QRectF(10,181.875-160*motion_metadata()[name]['baseline'],160,160)
                paint_walk(painter,target,name,state.gait_clock,state.gait_vector,energy=gait_energy,
                           eye_frame=state.idle.frame)
            painter.restore()
            return
        if now < state.message_until:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#eef7ff'))
            painter.drawRoundedRect(QRectF(43, 5, 94, 25), 12, 12)
            painter.setPen(QColor('#355a85'))
            painter.drawText(QRectF(43, 5, 94, 25), Qt.AlignmentFlag.AlignCenter, '喵～你好呀')
        # Keep the feet grounded and the asymmetric snowflake on its original side.
        painter.save()
        self.apply_click_reaction(painter, state, reaction)
        painter.translate(90, 185 - jump)
        painter.drawPixmap(QRectF(-80, -160, 160, 160),
                           self.motion_image(elapsed, state.idle.frame), QRectF(0, 0, 256, 256))
        painter.restore()

    @staticmethod
    @lru_cache(maxsize=1)
    def interaction_atlases():
        # These must survive ordinary action-atlas LRU eviction. The first
        # frame after release cannot afford PNG I/O and decoding.
        folder=Path(__file__).resolve().parent/'assets/actions'
        return {key:QPixmap(str(folder/key/'atlas.png')) for key in
                ('throw-flight','impact-left','impact-right','impact-ceiling','impact-floor')}

    @staticmethod
    @lru_cache(maxsize=6)
    def action_atlas(action_id):
        if action_id == 'music-waltz':
            from music_dance_asset import image
            decoded = image()
            if decoded is not None:
                return decoded
        pinned=PetRenderer.interaction_atlases().get(action_id)
        if pinned is not None:return pinned
        pinned=PetRenderer.click_atlases.get(action_id)
        if pinned is not None:return pinned
        return QPixmap(str(Path(__file__).resolve().parent / 'assets/actions' / action_id / 'atlas.png'))

    click_atlases = {}

    @staticmethod
    def prewarm_click_atlas(action_id):
        # Decoding a 1024x1536 atlas takes 20-45ms. Pay it while idle instead
        # of inside the first click, and pin it so ambient clips cannot evict
        # the response back into a cold decode.
        if action_id in PetRenderer.click_atlases:
            return
        path=Path(__file__).resolve().parent/'assets/actions'/action_id/'atlas.png'
        pixmap=QPixmap(str(path))
        if not pixmap.isNull():
            PetRenderer.click_atlases[action_id]=pixmap


class PetMenu:
    """创建右键菜单，并把用户选择交给窗口处理。"""

    def __init__(self, pet):
        self.pet = pet

    def show(self, event):
        if self.pet.controller is not None:
            if self.pet.state.music:
                self.pet.state.music.cancel()
            if self.pet.state.patrol:
                self.pet.state.patrol.interrupt('menu')
            menu = self.pet.controller.create_menu(self.pet)
            menu.exec(event.globalPos())
            menu.deleteLater()
            if self.pet.state.patrol:
                self.pet.state.patrol.settle_interruption(time.monotonic())


class DesktopPet(QWidget):
    """Qt 窗口：组合状态、动画、绘图和菜单，并接收鼠标事件。"""

    state_changed = Signal()
    position_settled = Signal()
    drag_finished = Signal()
    presence_entered = Signal()
    presence_exited = Signal()

    def __init__(self, preferences=None):
        super().__init__()
        self.preferences = preferences or Preferences()
        self.controller = None
        from snap_preview import SnapPreview
        self.snap_preview = SnapPreview(self)
        self.destroyed.connect(self.snap_preview.deleteLater)
        self.setWindowTitle('yuki · 桌面宠物')
        # Keep the window focusable: the context menu needs activation. Left
        # clicks are exempted from activation in nativeEvent below, because a
        # normal first click waits ~1.2s for the foreground handshake while the
        # workbench owns focus, which made the first drag feel frozen.
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 190)
        self.setMouseTracking(True)
        self.drag_origin = None
        self.press_position = None
        self.dragged = False
        self.caught_flight = False
        self.state = PetState()
        self.masker = WindowMask(self)
        self.presence = Presence()
        from dance_stage import DanceStage
        self.dance_stage = DanceStage(self)
        from dance_recovery import DanceRecovery
        self.dance_recovery = DanceRecovery(self)
        self.presence_timer = QTimer(self)
        self.presence_timer.setInterval(16)
        self.presence_timer.timeout.connect(self.advance_presence)
        self.click_x = 90.
        self.click_y = 95.
        self.click_zone = 'shy'
        self.press_started = 0.
        self.double_click = False
        self.renderer = PetRenderer()
        # Stagger the click responses so the idle first seconds never pay a
        # single long decode, and no user click ever waits for PNG I/O.
        for offset, action_id in enumerate(CLICK_REACTIONS):
            QTimer.singleShot(900+offset*150,
                              lambda key=action_id: PetRenderer.prewarm_click_atlas(key))
        self.memory_pending = {}
        self.memory_timer = QTimer(self)
        self.memory_timer.setSingleShot(True)
        self.memory_timer.setInterval(400)
        self.memory_timer.timeout.connect(self.flush_memory)
        # Follow the live cursor at display rate. Moving the window from every
        # WM_MOUSEMOVE let a backlog of stale positions trail the pointer for
        # up to a second while the click left the window behind.
        self.drag_follow_timer = QTimer(self)
        self.drag_follow_timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.drag_follow_timer.setInterval(FRAME_INTERVAL_MS)
        self.drag_follow_timer.timeout.connect(self.follow_drag_cursor)
        from drag_feedback import warm_assets
        warm_assets()
        self.animator = PetAnimator(self)
        self.menu = PetMenu(self)
        from pet_speech import SpeechBubble
        self.bubble = SpeechBubble(self)

        area = QApplication.primaryScreen().availableGeometry()
        self.state.position_x = float(area.right() - self.width() - 30)
        self.move(int(self.state.position_x), area.bottom() - self.height() + 1)
        self.apply_preferences(self.preferences)

    def screen_area(self):
        center = self.frameGeometry().center()
        screen = QApplication.screenAt(center)
        if screen is None:
            def distance(candidate):
                rectangle = candidate.availableGeometry()
                x = max(rectangle.left(), min(center.x(), rectangle.right()))
                y = max(rectangle.top(), min(center.y(), rectangle.bottom()))
                return (center.x() - x) ** 2 + (center.y() - y) ** 2
            screen = min(QApplication.screens(), key=distance)
        return screen.availableGeometry()

    def movement_allowed(self):
        return (not self.state.sleep.transitioning and self.isVisible() and self.drag_origin is None
                and not self.presence.active
                and not self.state.physics.active
                and not (self.state.music and self.state.music.active)
                and self.state.routine.period['walk'] > 0
                and not bool(getattr(self.controller, 'quick_pending', None))
                and not (self.bubble.parts and self.bubble.kind != 'ambient')
                and not (self.state.icon_sleep and self.state.icon_sleep.target)
                and not (self.state.edge_attachment and self.state.edge_attachment.active)
                and self.state.action_player.action is None
                and not self.preferences.paused and not self.preferences.quiet
                and self.preferences.random_movement)

    def record_gait(self,dx,dy,clock=None):
        distance=math.hypot(dx,dy)
        if distance>.001:
            self.state.gait_clock = clock if clock is not None else self.state.gait_clock+distance/(self.width()/180)
            self.state.gait_distance+=distance
            self.state.gait_until=time.monotonic()+.20
            if clock is None and abs(dx)>.01:self.state.direction=1 if dx>0 else -1

    def advance_to(self,target,dt,speed=None):
        now=time.monotonic()
        actual=(self.x(),self.y())
        position=self.state.travel_position
        # Compare with our last integer window command, not with its fractional
        # accumulator. Even a one-pixel external move starts from the new place.
        if position is None or actual != self.state.gait_window_position:position=actual
        route_start = self.state.travel_position is None
        previous=position
        length=math.hypot(target[0]-position[0],target[1]-position[1])
        if length < .001:
            self.state.travel_position=tuple(target)
            return True
        # Near-vertical travel must not flip on subpixel horizontal noise.
        direction = (1 if target[0]>position[0] else -1) if abs(target[0]-position[0])>.5 else self.state.direction
        vector=((target[0]-position[0])/length,(target[1]-position[1])/length)
        # Select the front/back rig per destination; repeated ticks for the
        # same destination keep one silhouette instead of flickering. A few
        # pixels of correction travel keep the current rig.
        target_key = tuple(target)
        if route_start or self.state.gait_name is None or target_key != self.state.gait_target:
            if length >= 6:
                self.state.gait_name = walking_name(direction, vector)
            elif self.state.gait_name is None:
                self.state.gait_name = 'walk-right' if direction > 0 else 'walk-left'
        self.state.gait_target = target_key
        name = self.state.gait_name
        stride=walk_stride(name)
        # Resume a settled route at a neutral half-stride instead of replaying
        # phase 0, which pops the legs when the last route stopped mid-step.
        if (route_start and now >= self.state.gait_until
                and self.state.current_gait_energy(now) <= .02):
            self.state.gait_clock = round(self.state.gait_clock/stride*2)/2*stride
        self.state.gait_direction = self.state.direction = direction
        self.state.gait_vector=vector
        distance, clock = gait_advance(self.state.gait_clock,name,
                                      self.preferences.speed if speed is None else speed,dt,self.width()/180,vector)
        clock=self.state.gait_clock+min(distance,length)/(self.width()/180)
        position,distance,arrived=step_towards(position,target,distance/.1,.1)
        self.state.travel_position=position
        self.move(*(round(v) for v in position))
        self.state.gait_window_position=(self.x(),self.y())
        self.state.gait_render_offset=tuple((v-a)/(self.width()/180) for v,a in zip(position,(self.x(),self.y())))
        self.record_gait(position[0]-previous[0],position[1]-previous[1],clock=clock)
        if math.hypot(position[0]-previous[0],position[1]-previous[1]) > .001:
            # A resumed walk keeps whatever strength remains, so a pause that
            # restarts quickly never makes the body drop and re-accelerate.
            energy = 0. if now-self.state.gait_energy_at > .18 else self.state.gait_energy
            self.state.gait_energy = min(1., energy+max(0.,min(.1,dt))/.14)
            self.state.gait_energy_at = now
        self.state.position_x=float(self.x())
        return arrived

    def moving(self, now=None):
        """True while the body is actually stepping, not merely while a route exists."""
        state = self.state
        if (self.presence.active or self.drag_origin is not None
                or state.physics.active or state.roll_path):
            return False
        now = time.monotonic() if now is None else now
        return (state.travel_target is not None or now < state.gait_until
                or state.current_gait_energy(now) > .02)

    def activity(self):
        """One live-state descriptor shared by the tray, IPC and the workbench."""
        state = self.state
        def report(key, label, posture=None, detail=''):
            return {'key': key, 'label': label, 'detail': detail, 'posture': posture}
        def patrol_report(posture=None):
            detail = {'walking': '正在走过去', 'observing': '正在观察',
                      'resting': '正在休息', 'doing': '正在互动',
                      'perched': '停在窗口边上', 'reacting': '正在回应',
                      'screen_passage': '正在绕到另一侧'}.get(state.patrol.phase, '')
            label = ('巡逻 · '+state.patrol.label
                     if state.patrol.exploring else state.patrol.label)
            return report('patrol', label, posture, detail)
        if not self.isVisible():
            return report('hidden', '已隐藏', detail='再次显示后会回到桌面')
        if self.presence.active:
            if self.presence.target:
                return report('entering', '探头 · 正在走来', detail='正走向上次关闭时的位置')
            return report('leaving', '回望 · 正在离开', detail='完全走出屏幕后才结束')
        if self.drag_origin is not None and self.dragged:
            return report('dragging', '拖动中', detail='松手后会落到最近的支撑面')
        if state.physics.active:
            if state.physics.impact_age < .3:
                label = {'left': '碰壁 · 弹回', 'right': '碰壁 · 弹回',
                         'ceiling': '碰顶 · 弹回', 'floor': '落地 · 回弹'}.get(
                             state.physics.impact, '抛掷 · 下落中')
            else:
                label = '抛掷 · 下落中' if state.physics.flying else '落地 · 缓一缓'
            return report('physics', label)
        if state.sleep.active:
            return report('sleeping', '熟睡中 · z z z', 'sleep',
                          '作息时段' if sleep_time() else '安静地睡着')
        if state.sleep.phase == 'waking':
            return report('waking', '睡觉待机 · 正在醒来', 'sleep')
        if state.icon_sleep and state.icon_sleep.target:
            return report('icon_sleep', state.icon_sleep.message, detail='靠在你桌面上的图标旁')
        if state.edge_attachment and state.edge_attachment.active:
            return report('attached', state.edge_attachment.message, detail='沿着屏幕边缘停靠')
        player = state.action_player
        if player.action is not None:
            action_id = player.action['id']
            posture = posture_for(action_id)
            performance = state.status_performance
            if (performance and player.started == performance.get('started')
                    and action_id == performance.get('action')):
                return report('status', performance['label'], posture, player.action['name'])
            focus = getattr(self, 'focus', None)
            if focus is not None and (focus.owns_action() or focus.owns_free()):
                return report('focus', '专注陪伴 · 安静地陪着你' if focus.phase == 'focus' else '专注休息 · 缓一缓',
                              posture)
            if state.music and state.music.active:
                music = state.music.snapshot()
                return report('music', music['reaction'], posture, music.get('label', ''))
            if state.patrol and state.patrol.active:
                return patrol_report(posture)
            if state.ambient.current and player.started == state.ambient.current[1] and posture:
                if player.action.get('lazy_roll'):
                    return report('action', '动作 · ' + player.action['name'], posture)
                return report('idle', STATES[posture]['name'] + '待机 · ' + player.action['name'],
                              posture, player.action['name'])
            return report('action', '动作 · ' + player.action['name'], posture, player.action['name'])
        if state.jump_started is not None:
            return report('jumping', '跳跃中')
        focus = getattr(self, 'focus', None)
        if focus is not None and focus.active and focus.base().focus_companion:
            return report('focus', '专注陪伴 · 安静地陪着你' if focus.phase == 'focus' else '专注休息 · 缓一缓')
        if self.preferences.quiet:
            return report('quiet', '安静模式', detail='减少主动打扰，仍留在桌面')
        if self.preferences.paused:
            return report('paused', '已暂停', detail='走动暂停，呼吸与手动动作保留')
        if state.patrol and (state.patrol.active or state.patrol.exploring):
            return patrol_report()
        if self.moving():
            return report('walking', '移动中', detail='正走向目的地')
        if not self.preferences.random_movement:
            return report('idle', '待机（随机移动已关闭）', 'stand', '随机走动已关闭')
        return report('idle', '站立待机 · ' + state.routine.period['name'], 'stand')

    def status_text(self):
        return self.activity()['label']

    def clamp_to_screen(self):
        self.state.physics.cancel()
        self.animator.timer.setInterval(FRAME_INTERVAL_MS)
        area = self.screen_area()
        factor = min(self.preferences.size / 100,
                     area.width() / 180, area.height() / 190)
        self.setFixedSize(max(1, round(180 * factor)), max(1, round(190 * factor)))
        x = max(area.left(), min(self.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(self.y(), area.bottom() - self.height() + 1))
        self.move(x, y)
        self.state.position_x = float(x)

    def go_home(self, primary=False):
        self.state.physics.cancel()
        self.wake_icon_sleep()
        area = (QApplication.primaryScreen().availableGeometry()
                if primary else self.screen_area())
        x = area.right() - self.width() - 30 if primary else self.x()
        self.state.travel_target=(x,area.bottom()-self.height()+1)
        self.state.travel_position=None

    def apply_preferences(self, preferences):
        rebuilt = (preferences.size != self.preferences.size
                   or preferences.always_on_top != self.preferences.always_on_top)
        if self.state.patrol and (preferences.paused or preferences.quiet or not preferences.random_movement
                                 or not preferences.autonomous_play
                                 or (not preferences.autonomous_icons and self.state.patrol.target is not None)
                                 or (not preferences.autonomous_windows and not self.state.patrol.demo
                                     and self.state.patrol.edge_is_window())
                                 or rebuilt):
            # A flag or size change rebuilds the native window; never keep the
            # old back-layer mask and z-order applied to the new one.
            self.state.patrol.suspend()
        presence = copy(self.presence) if self.presence.active else None
        if (hasattr(self,'state') and self.state.edge_attachment and rebuilt):
            self.state.edge_attachment.release()
        if (hasattr(self, 'state') and self.state.icon_sleep and self.state.icon_sleep.target
                and rebuilt):
            self.wake_icon_sleep()
        if hasattr(self, 'state') and rebuilt:
            self.state.sleep.clear_rest_site(self)
        previous = self.preferences
        self.preferences = preferences
        if self.state.music:
            self.state.music.sync()
        if hasattr(self, 'bubble'):
            self.bubble.sync_preferences()
        self.state.paused = preferences.paused
        visible = self.isVisible()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, preferences.always_on_top)
        if visible and not self.isVisible():
            self.show()
        self.setWindowOpacity(preferences.opacity / 100)
        bottom = self.y() + self.height()
        self.setFixedSize(round(180 * preferences.size / 100),
                          round(190 * preferences.size / 100))
        self.move(self.x(), bottom - self.height())
        self.clamp_to_screen()
        if rebuilt:
            self.masker.reapply()
        if preferences.quiet or not preferences.greeting:
            self.state.message_until = 0
        if not self.movement_allowed():
            self.state.walking = False
        self.update()
        if self.state.icon_sleep:
            self.state.icon_sleep.sync_watch()
        if presence is not None:
            # Changing a Qt window flag temporarily hides the widget. Keep the
            # requested fade direction instead of resurrecting a departing pet.
            self.presence = presence
            self.presence_timer.start()
            self.advance_presence()
        self.state_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.state.last_tick = time.monotonic()
        self.state.idle.reset(self.state.last_tick)
        self.animator.timer.start()
        self.state_changed.emit()

    def hideEvent(self, event):
        if hasattr(self, 'bubble'):
            self.bubble.hide()
        home = self.presence.home if self.presence.active else None
        self.presence_timer.stop()
        self.presence.reset(False)
        if home is not None:
            self.move(*(round(v) for v in home))
        self.wake_icon_sleep()
        super().hideEvent(event)
        self.animator.timer.stop()
        self.cancel_click()
        self.end_drag_feedback()
        self.snap_preview.clear()
        self.drag_origin = None
        self.state.walking = False
        self.state.jump_started = None
        self.state.message_until = 0
        self.state.action_player.stop()
        self.state_changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.paint_body(painter)
        painter.end()

    def paint_body(self, painter):
        if self.presence.active and self.presence.paint(painter):
            return
        if self.state.edge_attachment and self.state.edge_attachment.paint(painter):
            return
        if self.state.icon_sleep and self.state.icon_sleep.paint(painter):
            return
        factor=self.preferences.size/100 if self.state.drag_feedback else None
        scale=factor if factor is not None else min(self.width()/180,self.height()/190)
        painter.scale(scale,scale)
        self.renderer.draw(painter, self.state)

    def desired_visible(self):
        return self.presence.target if self.presence.active else self.isVisible()

    def present(self, visible):
        if visible == self.desired_visible():
            return
        self.cancel_click()
        self.end_drag_feedback()
        self.drag_origin = None
        self.snap_preview.clear()
        self.state.physics.cancel()
        self.state.walking = False
        self.state.gait_until = 0
        self.state.action_player.stop()
        self.state.jump_started = None
        self.state.message_until = 0
        self.state.click_reaction.clear()
        self.wake_icon_sleep()
        if self.state.edge_attachment:
            self.state.edge_attachment.release()
        if self.state.patrol:
            self.state.patrol.suspend()
        if self.state.music:
            self.state.music.cancel()
        self.state.sleep.wake(self, '显隐切换')
        self.masker.clear_all()
        if visible and not self.isVisible():
            self.clamp_to_screen()
            self.presence.reset(False)
            area = self.screen_area()
            self.presence.begin(True, position=(self.x(), self.y()),
                                area=area.getRect(), size=(self.width(), self.height()))
            self.move(*(round(v) for v in self.presence.origin))
            self.show()
        else:
            area = self.screen_area()
            self.presence.begin(visible, position=(self.x(), self.y()),
                                area=area.getRect(), size=(self.width(), self.height()))
        if self.presence.active:
            self.presence_timer.start()
        else:
            self.presence_timer.stop()
            if not visible:
                self.hide()
        self.update()
        self.state_changed.emit()

    def advance_presence(self, now=None):
        if not self.presence.active:
            self.presence_timer.stop()
            return
        complete = self.presence.update(now)
        self.move(*(round(v) for v in self.presence.position(now)))
        self.update()
        if complete:
            self.presence_timer.stop()
            if not self.presence.target:
                home = self.presence.home
                self.hide()
                self.move(*(round(v) for v in home))
                self.presence_exited.emit()
            else:
                self.state.last_tick = time.monotonic()
                self.state.started = self.state.last_tick
                self.state.idle.reset(self.state.last_tick)
                self.renderer.last_pose = None
                self.renderer.transition_image = None
                self.renderer.pointer_hold_image = None
                self.state.ambient.defer(self.state.last_tick, self.preferences.activity)
                self.presence_entered.emit()
            self.state_changed.emit()

    @staticmethod
    def _skips_activation(lparam):
        # WM_MOUSEACTIVATE stores the activating mouse message in the high
        # word of lParam (wParam is the window handle).
        return ((lparam >> 16) & 0xFFFF) in (0x0201, 0x0203)

    def nativeEvent(self, eventType, message):
        # MA_NOACTIVATE keeps the left-button message but skips the Windows
        # foreground handshake. Right clicks keep default activation so the
        # context menu can take focus.
        if eventType == b'windows_generic_MSG':
            msg = _NativeMessage.from_address(int(message))
            if msg.message == 0x0021 and self._skips_activation(msg.lParam):
                return True, 3
        return super().nativeEvent(eventType, message)

    def mousePressEvent(self, event):
        if self.state.patrol and self.desired_visible():
            self.state.patrol.record_pet_click()
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.desired_visible():
                event.ignore()
                return
            was_sleeping = self.state.sleep.transitioning
            self.state.sleep.wake(self, '点击或拖拽')
            if self.presence.active and self.presence.target:
                self.presence_entered.emit()
            self.presence_timer.stop()
            self.presence.reset(True)
            self.drag_follow_timer.stop()
            self.caught_flight = self.state.physics.active and self.state.physics.flying
            self.state.physics.cancel()
            point = event.globalPosition()
            self.state.pointer_velocity.reset(point.x(), point.y(), time.monotonic())
            self.double_click = False
            self.renderer.pointer_hold_image = None if was_sleeping else self.renderer.last_display_image
            self.renderer.transition_image = None
            # A press may become a drag. Do not show click feedback until the
            # gesture is classified; clearing a spring at the drag threshold
            # creates a one-frame pose flash.
            self.state.click_reaction.clear()
            self.wake_icon_sleep()
            self.click_x = event.position().x()*180/max(1,self.width())
            self.click_y = event.position().y()*190/max(1,self.height())
            self.click_zone = self.zone_for(self.click_y)
            self.press_started = time.monotonic()
            self.state.walking = False
            self.state.jump_started = None
            self.state.ambient.current = None
            self.state.ambient.defer(time.monotonic(), self.preferences.activity)
            self.drag_origin = event.globalPosition().toPoint() - self.pos()
            self.press_position = event.globalPosition().toPoint()
            self.dragged = False
            self.state.action_player.stop()
            if self.state.icon_sleep:
                self.state.icon_sleep.refresh()
            self.update()

    def cancel_click(self):
        self.renderer.pointer_hold_image = None
        self.double_click = False
        self.state.click_reaction.clear()

    @staticmethod
    def zone_for(y):
        if y < 190*.42:
            return 'shy'
        return 'body' if y < 190*.80 else 'feet'

    def play_click_reaction(self, kind):
        self.renderer.pointer_hold_image = None
        # A sleeping click already has its own approved wake-up response. Do
        # not start a standing shy/headpat clip underneath and cut it mid-clip.
        if self.state.sleep.phase == 'waking':
            self.update()
            return
        if self.state.music:
            self.state.music.cancel()
        if self.state.patrol:
            self.state.patrol.interrupt('click')
        self.state.walking = False
        self.state.gait_until = 0
        self.state.jump_started = None
        self.state.ambient.current = None
        self.state.ambient.defer(time.monotonic(), self.preferences.activity)
        player = self.state.action_player
        if kind == 'headpat':
            # Keep the full affection gesture; the click spring supplies the
            # jelly and repeated headpats restart it without suppression.
            player.play('affection')
            reaction = 'headpat'
        else:
            action_id = {'shy': 'shy', 'body': 'smile', 'feet': 'clicked'}.get(kind, 'shy')
            player.play(action_id)
            # A brief expression hold, not the authored gesture sequence.
            player.action = dict(player.action, durations=[1100 if action_id != 'clicked' else 900],
                                 click_expression=True)
            # The catalog names the authored expression pose, so re-cutting a
            # clip cannot leave the click holding a mid-motion frame.
            player.frame_order = [player.action.get('click_frame', 2)]
            reaction = {'shy': 'shy', 'body': 'happy', 'feet': 'startle'}.get(kind, 'shy')
        self.state.click_reaction.trigger(reaction, self.click_x)
        self.queue_memory('headpats' if kind == 'headpat' else 'clicks')
        self.update()
        self.state_changed.emit()

    def queue_memory(self, kind):
        # The counter lives in a JSON file written synchronously. A click must
        # never wait for the disk, and rapid headpats share one flush.
        if getattr(self.controller, 'memory', None) is None:
            return
        self.memory_pending[kind] = self.memory_pending.get(kind, 0) + 1
        if not self.memory_timer.isActive():
            self.memory_timer.start()

    def flush_memory(self):
        self.memory_timer.stop()
        pending, self.memory_pending = self.memory_pending, {}
        memory = getattr(self.controller, 'memory', None)
        if memory is None:
            return
        for kind, amount in pending.items():
            memory.record(kind, amount)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Qt sends press/release, double-click/release. Set up a possible
            # second-press drag while suppressing its trailing single click.
            self.mousePressEvent(event)
            self.double_click = True
            self.play_click_reaction('shy')
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None:
            point = event.globalPosition().toPoint()
            self.state.pointer_velocity.add(point.x(), point.y(), time.monotonic())
            if (point - self.press_position).manhattanLength() > QApplication.startDragDistance():
                if not self.dragged:
                    self.cancel_click()
                    self.state.sleep.interrupt_for_drag()
                    self.state.action_player.stop()
                    from drag_feedback import DragFeedback
                    factor=self.preferences.size/100
                    target=(self.drag_origin.x()/factor,self.drag_origin.y()/factor)
                    # Keep the native translucent window and pointer anchor
                    # unchanged. Resizing its backing surface on first movement
                    # allowed Windows to present a stale resized buffer.
                    self.state.drag_feedback=DragFeedback(target,compact=True)
                    self.state.drag_feedback.image(0)
                    self.animator.timer.setInterval(FRAME_INTERVAL_MS)
                    self.drag_follow_timer.start()
                self.dragged = True
            if self.dragged:
                # Track the event immediately; the display-rate follower then
                # re-anchors to the live cursor so a burst of queued moves
                # cannot trail the pointer for hundreds of pixels.
                self.move(point - self.drag_origin)
                self.state.position_x = float(self.x())
                self.snap_preview.queue(point)
                self.update()
        else:
            self.hover_direction = max(-1., min(1., (
                event.position().x()*180/max(1, self.width())-90)/80))
            self.hover_at = time.monotonic()
            self.hover_inside = True

    def follow_drag_cursor(self):
        if not self.dragged or self.drag_origin is None:
            self.drag_follow_timer.stop()
            return
        point = QCursor.pos()
        self.state.pointer_velocity.add(point.x(), point.y(), time.monotonic())
        position = point - self.drag_origin
        if position != self.pos():
            self.move(position)
            self.state.position_x = float(self.x())
        self.snap_preview.queue(point)
        self.update()

    def enterEvent(self, event):
        super().enterEvent(event)
        self.hover_at = time.monotonic()
        self.hover_inside = True

    def leaveEvent(self, event):
        if self.hover_inside:
            self.hover_at = time.monotonic()
            self.hover_inside = False
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_origin is not None:
            self.renderer.pointer_hold_image = None
            self.drop_point=event.globalPosition().toPoint()
            velocity = self.state.pointer_velocity.release(self.drop_point.x(), self.drop_point.y(), time.monotonic())
            self.end_drag_feedback()
            self.drag_origin = None
            if not self.dragged:
                if not self.double_click and self.isVisible():
                    held = time.monotonic()-self.press_started
                    kind = ('headpat' if self.click_zone == 'shy' and held >= .45
                            else self.click_zone)
                    self.play_click_reaction(kind)
                self.double_click = False
            elif self.state.action_player.action and self.state.action_player.action['id']=='dragged':
                self.state.action_player.stop()
            self.clamp_to_screen()
            if self.dragged:
                if self.state.patrol:
                    self.state.patrol.interrupt('drag')
                from drop_attachment import settle_drop
                attached = settle_drop(self,self.drop_point,cached_only=True)
                if not attached:
                    self.start_throw(velocity)
                self.snap_preview.clear()
                self.drag_finished.emit()
            elif self.caught_flight:
                # Catching a flying pet holds it only while the button is down.
                # Releasing without moving must not leave it floating midair.
                self.start_throw((0., 0.))
            self.caught_flight = False
            if not self.state.physics.active:
                self.position_settled.emit()
            self.update()
            self.state_changed.emit()

    def end_drag_feedback(self):
        self.animator.timer.setInterval(FRAME_INTERVAL_MS)
        self.drag_follow_timer.stop()
        self.snap_preview.timer.stop()
        self.snap_preview.hide()
        feedback=self.state.drag_feedback
        if feedback is None:return
        if feedback.compact:
            self.state.drag_feedback=None
            self.state.position_x=float(self.x())
            return
        factor=self.preferences.size/100
        dx,dy=feedback.body_origin()
        origin=self.pos()+QPoint(round((dx-10)*factor),round((dy-25)*factor))
        self.setUpdatesEnabled(False)
        try:
            self.state.drag_feedback=None
            self.setFixedSize(round(180*factor),round(190*factor))
            self.move(origin)
        finally:
            self.setUpdatesEnabled(True)
        self.state.position_x=float(self.x())

    def contextMenuEvent(self, event):
        self.menu.show(event)

    def start_throw(self, velocity):
        self.wake_icon_sleep()
        self.cancel_click()
        self.state.action_player.stop()
        self.state.ambient.current = None
        self.state.walking = False
        self.state.gait_until = 0
        self.state.jump_started = None
        self.state.last_tick = time.monotonic()
        self.state.physics.launch((self.x(), self.y()), velocity, self.width()/180)
        self.snap_preview.request_surfaces()
        self.animator.timer.start(FRAME_INTERVAL_MS)

    def advance_physics(self, dt):
        area = self.screen_area()
        edge=self.state.edge_attachment
        targets=[]
        if self.state.physics.flying and edge and self.preferences.auto_snap:
            self.snap_preview.request_surfaces()
            if time.monotonic()-self.snap_preview.surfaces_at<=.75:
                targets=edge.flight_targets(self.snap_preview.surfaces)
        settled = self.state.physics.step(dt, (area.left(), area.top(),
            area.right()-self.width()+1, area.bottom()-self.height()+1),
            (lambda start,end:edge.catch_flight(start,end,targets)) if targets else None)
        if edge and edge.active:
            self.position_settled.emit()
            return
        self.move(round(self.state.physics.x), round(self.state.physics.y))
        self.state.position_x = float(self.x())
        if settled:
            now = time.monotonic()
            self.state.ambient.defer(now, self.preferences.activity)
            self.animator.timer.start(FRAME_INTERVAL_MS)
            self.position_settled.emit()

    def wake_icon_sleep(self):
        perch = getattr(self, 'window_perch', None)
        if perch is not None and (perch.leaping or perch.attached):
            perch.cancel()
        if self.state.music:
            self.state.music.cancel()
        if self.state.patrol:
            self.state.patrol.suspend()
        self.state.physics.cancel()
        self.animator.timer.setInterval(FRAME_INTERVAL_MS)
        self.state.travel_target=None
        self.state.travel_position=None
        self.state.gait_until=0
        if self.state.edge_attachment:
            self.state.edge_attachment.release()
        if self.state.icon_sleep and self.state.icon_sleep.target:
            self.state.icon_sleep.wake()


def make_pet_icon():
    """复用实际角色生成图标，无需额外图片文件。"""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.scale(64 / 180, 64 / 190)
    PetRenderer().draw(painter, PetState())
    painter.end()
    return QIcon(pixmap)
