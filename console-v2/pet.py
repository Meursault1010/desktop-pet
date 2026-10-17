"""A small Windows-friendly desktop cat. Run with Python 3.10+."""
import math
import random
import time
from pathlib import Path
from functools import lru_cache

from idle_animation import IdleAnimation, motion_phase
from action_player import ActionPlayer, catalog
from locomotion import frame as motion_frame, step_towards

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
        self.icon_sleep = None
        self.edge_attachment = None
        self.gait_distance = 0.
        self.gait_until = 0.
        self.travel_target = None
        self.travel_position = None
        self.drag_feedback = None


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

        previous = self.pet.status_text()
        if state.travel_target is not None:
            if self.pet.drag_origin is None and self.pet.isVisible():
                if self.pet.advance_to(state.travel_target,dt):
                    state.travel_target=None
                    self.pet.position_settled.emit()
        elif self.pet.movement_allowed():
            if now >= state.next_action:
                probability, interval = {
                    '少动': (0.25, (4, 8)),
                    '默认': (0.65, (2, 5)),
                    '活跃': (0.90, (1, 3)),
                }[self.pet.preferences.activity]
                state.walking = random.random() < probability
                state.direction = random.choice([-1, 1])
                state.next_action = now + random.uniform(*interval)
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

    def draw(self, painter, state):
        now = time.monotonic()
        elapsed = now - state.started
        jump = 0 if state.jump_started is None else 36 * math.sin(
            math.pi * max(0, min(1, (now - state.jump_started) / .65)))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if state.drag_feedback is not None:
            state.drag_feedback.paint(painter, now)
            return
        frame = state.action_player.frame(now)
        if frame is not None:
            action = state.action_player.action
            atlas = self.action_atlas(action['id'])
            painter.drawPixmap(QRectF(10, 25, 160, 160), atlas,
                               QRectF((frame % action['columns'])*256,
                                      (frame // action['columns'])*256, 256, 256))
            return
        if now < state.gait_until:
            name='walk-right' if state.direction>0 else 'walk-left'
            painter.drawPixmap(QRectF(10,185-160*.92578125,160,160),
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
    @lru_cache(maxsize=6)
    def action_atlas(action_id):
        return QPixmap(str(Path(__file__).resolve().parent / 'assets/actions' / action_id / 'atlas.png'))


class PetMenu:
    """创建右键菜单，并把用户选择交给窗口处理。"""

    def __init__(self, pet):
        self.pet = pet

    def show(self, event):
        if self.pet.controller is not None:
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
        self.setWindowTitle('小橘 · 桌面宠物')
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(180, 190)
        self.setMouseTracking(True)
        self.drag_origin = None
        self.press_position = None
        self.dragged = False
        self.state = PetState()
        self.renderer = PetRenderer()
        self.animator = PetAnimator(self)
        self.menu = PetMenu(self)

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
        if self.drag_origin is not None and self.dragged:
            return '拖动中'
        if self.state.icon_sleep and self.state.icon_sleep.target:
            return self.state.icon_sleep.message
        if self.state.edge_attachment and self.state.edge_attachment.active:
            return self.state.edge_attachment.message
        if self.state.action_player.action is not None:
            return '动作 · ' + self.state.action_player.action['name']
        if self.state.jump_started is not None:
            return '跳跃中'
        if self.preferences.quiet:
            return '安静模式'
        if self.preferences.paused:
            return '已暂停'
        if not self.preferences.random_movement:
            return '待机（随机移动已关闭）'
        return '移动中' if self.state.walking else '待机'

    def clamp_to_screen(self):
        area = self.screen_area()
        factor = min(self.preferences.size / 100,
                     area.width() / 180, area.height() / 190)
        self.setFixedSize(max(1, round(180 * factor)), max(1, round(190 * factor)))
        x = max(area.left(), min(self.x(), area.right() - self.width() + 1))
        y = max(area.top(), min(self.y(), area.bottom() - self.height() + 1))
        self.move(x, y)
        self.state.position_x = float(x)

    def go_home(self, primary=False):
        self.wake_icon_sleep()
        area = (QApplication.primaryScreen().availableGeometry()
                if primary else self.screen_area())
        x = area.right() - self.width() - 30 if primary else self.x()
        self.state.travel_target=(x,area.bottom()-self.height()+1)
        self.state.travel_position=None

    def apply_preferences(self, preferences):
        if (hasattr(self,'state') and self.state.edge_attachment
                and (self.preferences.size!=preferences.size or self.preferences.always_on_top!=preferences.always_on_top)):
            self.state.edge_attachment.release()
        if (hasattr(self, 'state') and self.state.icon_sleep and self.state.icon_sleep.target
                and (self.preferences.size != preferences.size
                     or self.preferences.always_on_top != preferences.always_on_top)):
            self.wake_icon_sleep()
        previous = self.preferences
        self.preferences = preferences
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
        self.state_changed.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.state.last_tick = time.monotonic()
        self.state.idle.reset(self.state.last_tick)
        self.animator.timer.start()
        self.state_changed.emit()

    def hideEvent(self, event):
        self.wake_icon_sleep()
        super().hideEvent(event)
        self.animator.timer.stop()
        self.end_drag_feedback()
        self.drag_origin = None
        self.state.walking = False
        self.state.jump_started = None
        self.state.message_until = 0
        self.state.action_player.stop()
        self.state_changed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        if self.state.edge_attachment and self.state.edge_attachment.paint(painter):
            painter.end()
            return
        if self.state.icon_sleep and self.state.icon_sleep.paint(painter):
            painter.end()
            return
        factor=self.preferences.size/100 if self.state.drag_feedback else None
        painter.scale(factor or self.width()/180, factor or self.height()/190)
        self.renderer.draw(painter, self.state)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.wake_icon_sleep()
            self.drag_origin = event.globalPosition().toPoint() - self.pos()
            self.press_position = event.globalPosition().toPoint()
            self.dragged = False
            self.state.action_player.stop()
            if self.state.icon_sleep:
                self.state.icon_sleep.refresh()

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None:
            point = event.globalPosition().toPoint()
            if (point - self.press_position).manhattanLength() > QApplication.startDragDistance():
                if not self.dragged:
                    from drag_feedback import DragFeedback
                    factor=self.preferences.size/100
                    target=(self.drag_origin.x()/factor,self.drag_origin.y()/factor)
                    self.state.drag_feedback=DragFeedback(target)
                    self.setFixedSize(round(420*factor),round(440*factor))
                    self.drag_origin=QPoint(round(210*factor),round(220*factor))
                self.dragged = True
            if self.dragged:
                self.move(point - self.drag_origin)
                self.state.position_x = float(self.x())
                self.state_changed.emit()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_origin is not None:
            self.drop_point=event.globalPosition().toPoint()
            self.end_drag_feedback()
            self.drag_origin = None
            if not self.dragged:
                self.animator.jump()
                if 'clicked' in catalog():
                    self.state.action_player.play('clicked')
            elif self.state.action_player.action and self.state.action_player.action['id']=='dragged':
                self.state.action_player.stop()
            self.clamp_to_screen()
            if self.dragged:
                from drop_attachment import settle_drop
                settle_drop(self,self.drop_point)
                self.drag_finished.emit()
            self.position_settled.emit()
            self.update()
            self.state_changed.emit()

    def end_drag_feedback(self):
        feedback=self.state.drag_feedback
        if feedback is None:return
        factor=self.preferences.size/100
        dx,dy=feedback.body_origin()
        origin=self.pos()+QPoint(round((dx-10)*factor),round((dy-25)*factor))
        self.state.drag_feedback=None
        self.setFixedSize(round(180*factor),round(190*factor))
        self.move(origin)
        self.state.position_x=float(self.x())

    def contextMenuEvent(self, event):
        self.menu.show(event)

    def wake_icon_sleep(self):
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
