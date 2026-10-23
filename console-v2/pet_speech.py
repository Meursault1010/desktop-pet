"""Non-activating, pointer-transparent companion speech window."""
import random
import time
from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


def pages(text, limit=120):
    text = text.strip()
    result = []
    while len(text) > limit:
        end = max((text.rfind(c, limit//2, limit) for c in '。！？\n.!? '), default=-1)
        end = end+1 if end >= limit//2 else limit
        result.append(text[:end].strip())
        text = text[end:].lstrip()
    if text:
        result.append(text)
    return result or ['…']


class SpeechBubble(QWidget):
    def __init__(self, pet):
        super().__init__(pet, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowDoesNotAcceptFocus | Qt.WindowType.WindowTransparentForInput |
                         Qt.WindowType.WindowStaysOnTopHint)
        self.pet = pet
        self.setObjectName('yuki-speech')
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.sync_preferences()
        self.setFixedWidth(278)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(17, 12, 17, 23)
        layout.setSpacing(7)
        self.heading = QLabel('YUKI · 心声')
        self.heading.setStyleSheet('color:#6990a9; font-size:10px; letter-spacing:1px;')
        self.copy = QLabel()
        self.copy.setTextFormat(Qt.TextFormat.PlainText)
        self.copy.setWordWrap(True)
        self.copy.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.copy.setFont(QFont('Microsoft YaHei UI', 10))
        self.copy.setStyleSheet('color:#2c485d; background:transparent; line-height:1.5;')
        self.counter = QLabel()
        self.counter.setStyleSheet('color:#7d99ac; font-size:10px;')
        layout.addWidget(self.heading)
        layout.addWidget(self.copy)
        layout.addWidget(self.counter)
        self.text = ''
        self.kind = 'ambient'
        self.streaming = False
        self.parts = []
        self.index = 0
        self.shown_chars = 0.
        self.elapsed = 0.
        self.page_age = 0.
        self.last_tick = time.monotonic()
        self.next_ambient = self.last_tick+random.uniform(25, 45)
        self.previous_ambient = None
        self.tail = 139.
        self.below = False
        self.timer = QTimer(self)
        self.timer.setInterval(40)
        self.timer.timeout.connect(self.tick)
        self.timer.start()

    def say(self, text, kind='chat', streaming=False):
        state = self.pet.state
        if kind == 'ambient' and (state.sleep.active or not self.pet.preferences.autonomous_speech):
            return
        if kind in ('chat', 'error'):
            state.sleep.wake(self.pet, '主动交流')
        if kind != 'ambient' and state.music:
            state.music.cancel()
        if kind != 'ambient' and state.patrol:
            state.patrol.interrupt('chat')
        if kind != 'ambient' and state.ambient.current and state.ambient.current[0] == 'sleep':
            state.action_player.stop()
            state.ambient.current = None
            state.ambient.defer(time.monotonic(), self.pet.preferences.activity)
        # Streaming updates keep their typing position, rather than restarting.
        continuation = kind == self.kind and self.streaming and text.startswith(self.text)
        self.text = text[:6000].strip()
        self.kind, self.streaming = kind, streaming
        self.parts = pages(self.text)
        if not continuation:
            self.index = 0
            self.shown_chars = 0.
            self.elapsed = 0.
        self.index = min(self.index, len(self.parts)-1)
        self.page_age = 0.
        self.next_ambient = time.monotonic()+random.uniform(90, 180)*self.pet.state.routine.period['speech']
        self.heading.setText('YUKI · 心声' if kind == 'ambient' else 'YUKI · 与你说话')
        self.layout_page()

    def layout_page(self):
        page = self.parts[self.index]
        # Reserve the final page's height while letters appear, avoiding jitter.
        self.copy.setText(page)
        height = max(24, self.copy.heightForWidth(244))
        self.copy.setFixedHeight(height)
        self.counter.setText(f'{self.index+1} / {len(self.parts)}' if len(self.parts)>1 else ' ')
        self.adjustSize()
        self.copy.setText(page[:int(self.shown_chars)])

    def clear(self):
        self.text = ''
        self.parts = []
        self.hide()

    def sync_preferences(self):
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.pet.preferences.always_on_top)

    def available(self):
        pet = self.pet
        return (not pet.state.sleep.active and pet.isVisible() and pet.desired_visible() and not pet.presence.active
                and pet.drag_origin is None and not pet.state.physics.active)

    def position_near_pet(self):
        area = self.pet.screen_area()
        cx = self.pet.x()+self.pet.width()/2
        x = round(max(area.left(), min(area.right()-self.width()+1, cx-self.width()/2)))
        above = self.pet.y()-self.height()+18
        y = above if above >= area.top() else self.pet.y()+self.pet.height()-15
        y = max(area.top(), min(area.bottom()-self.height()+1, y))
        self.tail = max(24., min(self.width()-24., cx-x))
        self.below = above < area.top()
        self.move(x, round(y))

    def tick(self):
        now = time.monotonic()
        dt = max(0., min(.15, now-self.last_tick))
        self.last_tick = now
        if not self.available():
            self.timer.setInterval(200)
            self.hide()
            return
        self.timer.setInterval(40)
        if not self.parts:
            state = self.pet.state
            if (now >= self.next_ambient and not self.pet.preferences.quiet
                    and self.pet.preferences.autonomous_speech
                    and not self.pet.preferences.paused and not state.walking
                    and state.action_player.action is None
                    and not bool(getattr(self.pet.controller, 'quick_pending', None))):
                choices = [s for s in state.routine.period['lines'] if s != self.previous_ambient]
                self.previous_ambient = random.choice(choices)
                self.say(self.previous_ambient, 'ambient')
            return
        if self.kind == 'ambient' and self.pet.preferences.quiet:
            self.clear()
            return
        self.elapsed += dt
        page = self.parts[self.index]
        self.shown_chars = min(len(page), self.shown_chars+dt*36)
        self.copy.setText(page[:int(self.shown_chars)])
        hold = max(6., len(page)*.075)
        if self.shown_chars >= len(page) and not self.streaming:
            self.page_age += dt
        fade = min(1., self.elapsed/.2)
        if self.page_age > hold:
            if self.index+1 < len(self.parts):
                self.index += 1
                self.shown_chars = self.page_age = 0.
                self.layout_page()
            else:
                fade *= max(0., 1-(self.page_age-hold)/.35)
                if fade <= 0:
                    self.clear()
                    return
        self.setWindowOpacity(fade*self.pet.preferences.opacity/100)
        self.position_near_pet()
        if not self.isVisible():
            self.show()
        self.update()

    def apply_theme(self, theme):
        self.bubble_theme = theme
        dark = theme == 'dark'
        self.copy.setStyleSheet('color:' + ('#e1eaf3' if dark else '#2c485d') + '; background:transparent;')
        for label in (self.heading, self.counter):
            label.setStyleSheet('color:' + ('#a6b8c9' if dark else '#53697a') + ';font-size:10px;')
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = getattr(self, 'bubble_theme', 'mist')
        painter.setPen(QPen(QColor('#34485d' if theme == 'dark' else '#c7dce9'), 1))
        painter.setBrush(QColor('#192838' if theme == 'dark' else '#fcfdfe' if theme == 'light' else '#e3eff7'))
        painter.drawRoundedRect(1, 1, self.width()-2, self.height()-12, 13, 13)
        painter.setPen(Qt.PenStyle.NoPen)
        if not self.below:
            painter.drawPolygon(QPolygonF([QPointF(self.tail-7, self.height()-12),
                QPointF(self.tail, self.height()-3), QPointF(self.tail+7, self.height()-12)]))
        painter.end()
