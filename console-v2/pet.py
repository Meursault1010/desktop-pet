"""A small Windows-friendly desktop cat. Run with Python 3.10+."""
import math
import random
import time
from copy import copy
from pathlib import Path
from functools import lru_cache

from idle_animation import IdleAnimation, motion_phase
from action_player import ActionPlayer, catalog
from idle_actions import IdleActions
from click_reaction import ClickReaction
from pet_physics import PetPhysics, PointerVelocity
from pet_presence import Presence
from daily_routine import DailyRoutine
from locomotion import frame as motion_frame, step_towards, metadata as motion_metadata

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from settings_model import Preferences


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
        self.next_action = self.started + 3
        self.idle = IdleAnimation(now=self.started)
        self.action_player = ActionPlayer()
        self.ambient = IdleActions()
        self.routine = DailyRoutine()
        self.ambient.set_period(self.routine.period)
        self.ambient.defer(self.started)
        self.ambient.next_at=self.started+random.uniform(5,8)
        self.icon_sleep = None
        self.edge_attachment = None
        self.gait_distance = 0.
        self.gait_until = 0.
        self.travel_target = None
        self.travel_position = None
        self.drag_feedback = None
        self.click_reaction = ClickReaction()
        self.physics = PetPhysics()
        self.pointer_velocity = PointerVelocity()
        self.patrol = None
        self.music = None


class PetAnimator:
    """负责定时更新移动和跳跃状态。"""

    def __init__(self, pet):
        self.pet = pet
        self.timer = QTimer(pet)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def tick(self):
        state = self.pet.state
        now = time.monotonic()
        dt = min(now - state.last_tick, 0.1)
        state.last_tick = now
        state.idle.update(now)
        state.action_player.frame(now)
        if state.music:
            state.music.tick(now)
        if state.patrol:
            state.patrol.tick(now, dt)
        self.update_ambient(now)

        previous = self.pet.status_text()
        if self.pet.presence.active:
            state.walking = False
        elif state.physics.active:
            self.pet.advance_physics(dt)
        elif state.travel_target is not None:
            if self.pet.drag_origin is None and self.pet.isVisible():
                if self.pet.advance_to(state.travel_target,dt):
                    state.travel_target=None
                    self.pet.position_settled.emit()
        elif state.patrol and state.patrol.active:
            state.walking = False
        elif self.pet.movement_allowed() and state.patrol is None:
            if now >= state.next_action:
                probability, interval = {
                    '少动': (0.08, (14, 22)),
                    '默认': (0.15, (10, 18)),
                    '活跃': (0.25, (7, 12)),
                }[self.pet.preferences.activity]
                probability *= state.routine.period['walk']
                state.walking = random.random() < probability
                state.direction = random.choice([-1, 1])
                state.next_action = now + random.uniform(*( (1, 2.5) if state.walking else interval))
            if state.walking:
                area = self.pet.screen_area()
                low = area.left()
                high = max(low, area.right() - self.pet.width() + 1)
                state.position_x += state.direction * self.pet.preferences.speed * dt
                if state.position_x <= low or state.position_x >= high:
                    state.direction *= -1
                state.position_x = max(low, min(high, state.position_x))
                old=self.pet.x()
                self.pet.move(round(state.position_x), self.pet.y())
                self.pet.record_gait(self.pet.x()-old,0)
        else:
            state.walking = False

        if state.jump_started is not None and now - state.jump_started >= 0.65:
            state.jump_started = None
        self.pet.update()
        if previous != self.pet.status_text():
            self.pet.state_changed.emit()

    def update_ambient(self, now):
        pet = self.pet
        state = pet.state
        ambient = state.ambient
        player = state.action_player
        changed = state.routine.update()
        if changed or ambient.period_key != state.routine.period['key']:
            ambient.set_period(state.routine.period)
            state.walking = False
            state.next_action = now
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
                   or bool(state.patrol and state.patrol.active)
                   or bool(state.music and state.music.active)
                   or state.travel_target is not None
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
                        player.play(followup, now=seated_start)
                        ambient.current = (followup, seated_start, float(pet.x()),
                                           sum(player.action['durations'])/1000)
                        return
        if blocked or player.action is not None:
            if blocked:
                ambient.defer(now, pet.preferences.activity)
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
        sleeping = key == 'sleep' and state.routine.period['key'] == 'night'
        player.play(key, now=now, loop=sleeping)
        duration = random.uniform(70, 140) if sleeping else sum(player.action['durations'])/1000
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
        pose = ('physics',) if state.physics.active else ('action', action['id'], state.action_player.started) if action else (
            ('walk', state.direction) if now < state.gait_until else ('idle',))
        image = QImage(180, 190, QImage.Format.Format_RGBA32FPx4_Premultiplied)
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
            self.transition_image = self.last_image if self.transition_duration else None
            self.transition_started = now
        progress = min(1., max(0., (now-self.transition_started)/self.transition_duration)) if self.transition_duration else 1.
        if self.transition_image is not None and progress < 1:
            # Smoothstep eases both ends; weighted addition preserves alpha at
            # overlapping translucent edges instead of flashing brighter.
            weight = progress*progress*(3-2*progress)
            mixed = QImage(image.size(), image.format())
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
        displayed.fill(Qt.GlobalColor.transparent)
        display = QPainter(displayed)
        dx, dy, angle, scale_x, scale_y, shear = state.click_reaction.transform(now)
        if state.music:
            mx, my, tilt = state.music.transform(now)
            dx += mx
            dy += my
            angle += tilt
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

    def draw_pose(self, painter, state):
        now = time.monotonic()
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
            painter.drawPixmap(QRectF(10, 25, 160, 160), atlas,
                               QRectF((frame % 4)*256, (frame // 4)*256, 256, 256))
            return
        frame = state.action_player.frame(now)
        if frame is not None:
            action = state.action_player.action
            if action.get('pixel_art'):
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
            atlas = self.action_atlas(action['id'])
            painter.drawPixmap(QRectF(10, 25, 160, 160), atlas,
                               QRectF((frame % action['columns'])*256,
                                      (frame // action['columns'])*256, 256, 256))
            return
        if now < state.gait_until:
            name='walk-right' if state.direction>0 else 'walk-left'
            painter.drawPixmap(QRectF(10,181.875-160*motion_metadata()[name]['baseline'],160,160),
                               motion_frame(name,state.gait_distance),QRectF(0,0,256,256))
            return
        if now < state.message_until:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#eef7ff'))
            painter.drawRoundedRect(QRectF(43, 5, 94, 25), 12, 12)
            painter.setPen(QColor('#355a85'))
            painter.drawText(QRectF(43, 5, 94, 25), Qt.AlignmentFlag.AlignCenter, '喵～你好呀')
        # Keep the feet grounded and the asymmetric snowflake on its original side.
        painter.save()
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
        pinned=PetRenderer.interaction_atlases().get(action_id)
        if pinned is not None:return pinned
        return QPixmap(str(Path(__file__).resolve().parent / 'assets/actions' / action_id / 'atlas.png'))


class PetMenu:
    """创建右键菜单，并把用户选择交给窗口处理。"""

    def __init__(self, pet):
        self.pet = pet

    def show(self, event):
        if self.pet.controller is not None:
            if self.pet.state.music:
                self.pet.state.music.cancel()
            if self.pet.state.patrol:
                self.pet.state.patrol.cancel()
            menu = self.pet.controller.create_menu(self.pet)
            menu.exec(event.globalPos())
            menu.deleteLater()


class DesktopPet(QWidget):
    """Qt 窗口：组合状态、动画、绘图和菜单，并接收鼠标事件。"""

    state_changed = Signal()
    position_settled = Signal()
    drag_finished = Signal()

    def __init__(self, preferences=None):
        super().__init__()
        self.preferences = preferences or Preferences()
        self.controller = None
        from snap_preview import SnapPreview
        self.snap_preview = SnapPreview(self)
        self.destroyed.connect(self.snap_preview.deleteLater)
        self.setWindowTitle('yuki · 桌面宠物')
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
        self.presence = Presence()
        self.presence_timer = QTimer(self)
        self.presence_timer.setInterval(16)
        self.presence_timer.timeout.connect(self.advance_presence)
        self.click_timer = QTimer(self)
        self.click_timer.setSingleShot(True)
        self.click_timer.timeout.connect(self.finish_single_click)
        self.click_x = 90.
        self.double_click = False
        self.renderer = PetRenderer()
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
        return (self.isVisible() and self.drag_origin is None
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

    def record_gait(self,dx,dy):
        distance=math.hypot(dx,dy)
        if distance>.001:
            self.state.gait_distance+=distance
            self.state.gait_until=time.monotonic()+.09
            if abs(dx)>.01:self.state.direction=1 if dx>0 else -1

    def advance_to(self,target,dt,speed=None):
        actual=(self.x(),self.y())
        position=self.state.travel_position
        if position is None or any(abs(a-b)>1.1 for a,b in zip(position,actual)):position=actual
        previous=position
        position,distance,arrived=step_towards(position,target,speed or max(65,self.preferences.speed),dt)
        self.state.travel_position=position
        self.move(*(round(v) for v in position))
        self.record_gait(position[0]-previous[0],position[1]-previous[1])
        self.state.position_x=float(self.x())
        return arrived

    def status_text(self):
        if not self.isVisible():
            return '已隐藏'
        if self.presence.active:
            return '星光 · 正在出现' if self.presence.target else '星光 · 轻轻隐去'
        if self.drag_origin is not None and self.dragged:
            return '拖动中'
        if self.state.physics.active:
            if self.state.physics.impact_age < .3:
                return {'left': '碰壁 · 弹回', 'right': '碰壁 · 弹回',
                        'ceiling': '碰顶 · 弹回', 'floor': '落地 · 回弹'}.get(
                            self.state.physics.impact, '抛掷 · 下落中')
            return '抛掷 · 下落中' if self.state.physics.flying else '落地 · 缓一缓'
        if self.state.icon_sleep and self.state.icon_sleep.target:
            return self.state.icon_sleep.message
        if self.state.edge_attachment and self.state.edge_attachment.active:
            return self.state.edge_attachment.message
        if self.state.action_player.action is not None:
            if self.state.music and self.state.music.active:
                return self.state.music.snapshot()['reaction']
            if self.state.patrol and self.state.patrol.active:
                return self.state.patrol.label
            return '动作 · ' + self.state.action_player.action['name']
        if self.state.jump_started is not None:
            return '跳跃中'
        if self.preferences.quiet:
            return '安静模式'
        if self.preferences.paused:
            return '已暂停'
        if not self.preferences.random_movement:
            return '待机（随机移动已关闭）'
        if self.state.patrol and self.state.patrol.active:
            return self.state.patrol.label
        return '移动中' if self.state.walking else '待机 · ' + self.state.routine.period['name']

    def clamp_to_screen(self):
        self.state.physics.cancel()
        self.animator.timer.setInterval(33)
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
        if self.state.patrol and (preferences.paused or preferences.quiet or not preferences.random_movement
                                 or preferences.size != self.preferences.size):
            self.state.patrol.cancel()
        presence = copy(self.presence) if self.presence.active else None
        if (hasattr(self,'state') and self.state.edge_attachment
                and (self.preferences.size!=preferences.size or self.preferences.always_on_top!=preferences.always_on_top)):
            self.state.edge_attachment.release()
        if (hasattr(self, 'state') and self.state.icon_sleep and self.state.icon_sleep.target
                and (self.preferences.size != preferences.size
                     or self.preferences.always_on_top != preferences.always_on_top)):
            self.wake_icon_sleep()
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
        if preferences.quiet or not preferences.greeting:
            self.state.message_until = 0
        if not self.movement_allowed():
            self.state.walking = False
        if any(getattr(previous, name) != getattr(preferences, name)
               for name in ('paused', 'quiet', 'random_movement', 'activity')):
            self.state.next_action = time.monotonic()
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
        self.presence_timer.stop()
        self.presence.reset(False)
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
        painter.save()
        if self.presence.active:
            opacity, lift, sx, sy = self.presence.body()
            painter.setOpacity(opacity)
            painter.translate(self.width()/2, self.height()*.94+lift*self.height()/190)
            painter.scale(sx, sy)
            painter.translate(-self.width()/2, -self.height()*.94)
        self.paint_body(painter)
        painter.restore()
        if self.presence.active:
            painter.scale(self.width()/180, self.height()/190)
            self.presence.paint_stars(painter)
        painter.end()

    def paint_body(self, painter):
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
        if visible and not self.isVisible():
            self.clamp_to_screen()
            self.presence.reset(False)
            # Set zero opacity in paint before QWidget is first shown.
            self.presence.begin(True)
            self.show()
        else:
            self.presence.begin(visible)
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
        self.update()
        if complete:
            self.presence_timer.stop()
            if not self.presence.target:
                self.hide()
            else:
                self.state.last_tick = time.monotonic()
                self.state.ambient.defer(self.state.last_tick, self.preferences.activity)
            self.state_changed.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.desired_visible():
                event.ignore()
                return
            self.presence_timer.stop()
            self.presence.reset(True)
            self.caught_flight = self.state.physics.active and self.state.physics.flying
            self.state.physics.cancel()
            point = event.globalPosition()
            self.state.pointer_velocity.reset(point.x(), point.y(), time.monotonic())
            self.click_timer.stop()
            self.double_click = False
            self.renderer.pointer_hold_image = self.renderer.last_display_image
            self.snap_preview.request_surfaces()
            self.renderer.transition_image = None
            # A press may become a drag. Do not show click feedback until the
            # gesture is classified; clearing a spring at the drag threshold
            # creates a one-frame pose flash.
            self.state.click_reaction.clear()
            self.wake_icon_sleep()
            self.click_x = event.position().x()*180/max(1,self.width())
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
        self.click_timer.stop()
        self.double_click = False
        self.state.click_reaction.clear()

    def finish_single_click(self):
        if self.isVisible() and self.drag_origin is None:
            self.play_click_reaction('shy')

    def play_click_reaction(self, kind):
        self.renderer.pointer_hold_image = None
        if self.state.music:
            self.state.music.cancel()
        if self.state.patrol:
            self.state.patrol.cancel()
        self.state.walking = False
        self.state.gait_until = 0
        self.state.jump_started = None
        self.state.ambient.current = None
        self.state.ambient.defer(time.monotonic(), self.preferences.activity)
        self.state.action_player.play('affection' if kind == 'headpat' else 'shy')
        self.state.click_reaction.trigger(kind, self.click_x)
        self.update()
        self.state_changed.emit()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Qt sends press/release, double-click/release. Set up a possible
            # second-press drag while suppressing its trailing single click.
            self.mousePressEvent(event)
            self.double_click = True
            self.play_click_reaction('headpat')
            event.accept()

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None:
            point = event.globalPosition().toPoint()
            moved = False
            self.state.pointer_velocity.add(point.x(), point.y(), time.monotonic())
            if (point - self.press_position).manhattanLength() > QApplication.startDragDistance():
                if not self.dragged:
                    self.cancel_click()
                    self.state.action_player.stop()
                    from drag_feedback import DragFeedback
                    factor=self.preferences.size/100
                    target=(self.drag_origin.x()/factor,self.drag_origin.y()/factor)
                    # Keep the native translucent window and pointer anchor
                    # unchanged. Resizing its backing surface on first movement
                    # allowed Windows to present a stale resized buffer.
                    self.state.drag_feedback=DragFeedback(target,compact=True)
                    self.state.drag_feedback.image(0)
                    self.animator.timer.setInterval(16)
                self.dragged = True
            if self.dragged:
                if not moved:
                    self.move(point - self.drag_origin)
                self.state.position_x = float(self.x())
                self.snap_preview.queue(point)
                self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_origin is not None:
            self.renderer.pointer_hold_image = None
            self.drop_point=event.globalPosition().toPoint()
            velocity = self.state.pointer_velocity.release(self.drop_point.x(), self.drop_point.y(), time.monotonic())
            self.end_drag_feedback()
            self.drag_origin = None
            if not self.dragged:
                if not self.double_click:
                    self.click_timer.start(QApplication.doubleClickInterval())
                self.double_click = False
            elif self.state.action_player.action and self.state.action_player.action['id']=='dragged':
                self.state.action_player.stop()
            self.clamp_to_screen()
            if self.dragged:
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
        self.animator.timer.setInterval(33)
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
        self.animator.timer.start(16)

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
            self.state.next_action = now+random.uniform(8, 14)
            self.animator.timer.start(33)
            self.position_settled.emit()

    def wake_icon_sleep(self):
        if self.state.music:
            self.state.music.cancel()
        if self.state.patrol:
            self.state.patrol.cancel()
        self.state.physics.cancel()
        self.animator.timer.setInterval(33)
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
