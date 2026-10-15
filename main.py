"""A small Windows-friendly desktop cat. Run with Python 3.10+."""
import math
import random
import sys
import time

from PySide6.QtCore import QPoint, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QApplication, QMenu, QWidget


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

        if self.pet.drag_origin is None and not state.paused:
            if now >= state.next_action:
                state.walking = random.choice([True, True, False])
                state.direction = random.choice([-1, 1])
                state.next_action = now + random.uniform(2, 5)
            if state.walking:
                area = self.pet.screen_area()
                low = area.left()
                high = max(low, area.right() - self.pet.width() + 1)
                state.position_x += state.direction * 48 * dt
                if state.position_x <= low or state.position_x >= high:
                    state.direction *= -1
                state.position_x = max(low, min(high, state.position_x))
                self.pet.move(round(state.position_x), self.pet.y())

        if state.jump_started is not None and now - state.jump_started >= 0.65:
            state.jump_started = None
        self.pet.update()

    def jump(self):
        now = time.monotonic()
        self.pet.state.jump_started = now
        self.pet.state.message_until = now + 1.5


class PetRenderer:
    """只负责把宠物当前状态绘制到 QPainter。"""

    def draw(self, painter, state):
        now = time.monotonic()
        elapsed = now - state.started
        jump = 0 if state.jump_started is None else 36 * math.sin(
            math.pi * min(1, (now - state.jump_started) / 0.65)
        )
        bob = math.sin(elapsed * (12 if state.walking and not state.paused else 3)) * 2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if now < state.message_until:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#fff7e7'))
            painter.drawRoundedRect(QRectF(43, 5, 94, 25), 12, 12)
            painter.setPen(QColor('#6b422d'))
            painter.drawText(QRectF(43, 5, 94, 25), Qt.AlignmentFlag.AlignCenter, '喵～你好呀')

        painter.translate(90, 111 - jump + bob)
        painter.scale(state.direction, 1)
        outline = QPen(QColor('#79492e'), 3, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(outline)
        painter.setBrush(QColor('#efa34b'))
        painter.drawEllipse(QRectF(27, 6, 37, 15))
        painter.drawEllipse(QRectF(-34, -4, 68, 61))

        step = math.sin(elapsed * 12) * 5 if state.walking and not state.paused else 0
        painter.drawEllipse(QRectF(-31 + step, 43, 25, 16))
        painter.drawEllipse(QRectF(7 - step, 43, 25, 16))
        painter.drawPolygon([QPoint(-39, -23), QPoint(-37, -62), QPoint(-9, -42)])
        painter.drawPolygon([QPoint(9, -42), QPoint(37, -62), QPoint(39, -23)])
        painter.drawEllipse(QRectF(-45, -49, 90, 69))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#ffe4b6'))
        painter.drawEllipse(QRectF(-18, 12, 36, 35))
        painter.drawEllipse(QRectF(-26, -15, 52, 29))
        painter.setPen(QPen(QColor('#573c30'), 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        blink = elapsed % 4.2 > 4.02
        for x in (-19, 19):
            if blink:
                painter.drawLine(x - 4, -22, x + 4, -22)
            else:
                painter.drawEllipse(QRectF(x - 2, -27, 4, 8))
        painter.drawLine(-3, -10, 3, -10)
        painter.drawLine(0, -10, 0, -5)
        painter.drawArc(QRectF(-10, -11, 10, 12), 180 * 16, 150 * 16)
        painter.drawArc(QRectF(0, -11, 10, 12), 210 * 16, 150 * 16)
        painter.setPen(QPen(QColor('#b87536'), 3, Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap))
        for x in (-10, 0, 10):
            painter.drawLine(x, -46, x, -37)


class PetMenu:
    """创建右键菜单，并把用户选择交给窗口处理。"""

    def __init__(self, pet):
        self.pet = pet

    def show(self, event):
        menu = QMenu(self.pet)
        pause = menu.addAction('继续活动' if self.pet.state.paused else '暂停走动')
        jump = menu.addAction('跳一下')
        home = menu.addAction('回到桌面底部')
        menu.addSeparator()
        quit_action = menu.addAction('退出小橘')
        selected = menu.exec(event.globalPos())
        if selected == pause:
            self.pet.state.paused = not self.pet.state.paused
        elif selected == jump:
            self.pet.animator.jump()
        elif selected == home:
            self.pet.move(self.pet.x(), self.pet.screen_area().bottom() - self.pet.height() + 1)
        elif selected == quit_action:
            QApplication.quit()


class DesktopPet(QWidget):
    """Qt 窗口：组合状态、动画、绘图和菜单，并接收鼠标事件。"""

    def __init__(self):
        super().__init__()
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

    def screen_area(self):
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        return screen.availableGeometry()

    def paintEvent(self, event):
        painter = QPainter(self)
        self.renderer.draw(painter, self.state)
        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_origin = event.globalPosition().toPoint() - self.pos()
            self.press_position = event.globalPosition().toPoint()
            self.dragged = False

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None:
            point = event.globalPosition().toPoint()
            if (point - self.press_position).manhattanLength() > QApplication.startDragDistance():
                self.dragged = True
            if self.dragged:
                self.move(point - self.drag_origin)
                self.state.position_x = float(self.x())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drag_origin is not None:
            self.drag_origin = None
            if not self.dragged:
                self.animator.jump()
            area = self.screen_area()
            x = max(area.left(), min(self.x(), max(area.left(), area.right() - self.width() + 1)))
            y = max(area.top(), min(self.y(), max(area.top(), area.bottom() - self.height() + 1)))
            self.move(x, y)
            self.state.position_x = float(x)

    def contextMenuEvent(self, event):
        self.menu.show(event)


def main():
    app = QApplication(sys.argv)
    pet = DesktopPet()
    pet.show()
    if '--smoke-test' in sys.argv:
        pet.animator.jump()
        QTimer.singleShot(800, app.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
