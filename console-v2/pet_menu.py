"""Shared, keyboard-accessible menu for the pet and the system tray."""
from PySide6.QtCore import QSize, Qt, QTimer, QVariantAnimation, QPointF
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMenu, QToolButton, QVBoxLayout, QWidget, QWidgetAction


def menu_icon(kind):
    image = QPixmap(20, 20)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor('#527b97'), 1.6, Qt.PenStyle.SolidLine,
                        Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
    if kind == 'console':
        painter.drawRoundedRect(3, 3, 14, 14, 2, 2)
        painter.drawLine(3, 7, 17, 7)
        painter.drawLine(8, 7, 8, 17)
    elif kind == 'visibility':
        painter.drawEllipse(3, 5, 14, 10)
        painter.drawEllipse(8, 8, 4, 4)
    elif kind == 'pause':
        painter.drawLine(7, 5, 7, 15)
        painter.drawLine(13, 5, 13, 15)
    elif kind == 'home':
        painter.drawLine(10, 3, 10, 13)
        painter.drawLine(6, 9, 10, 13)
        painter.drawLine(14, 9, 10, 13)
        painter.drawLine(4, 17, 16, 17)
    elif kind == 'detach':
        painter.drawArc(4, 4, 12, 12, 40 * 16, 280 * 16)
        painter.drawLine(15, 3, 16, 8)
        painter.drawLine(16, 8, 11, 7)
    elif kind == 'exit':
        painter.drawArc(4, 4, 12, 12, 130 * 16, 280 * 16)
        painter.drawLine(10, 2, 10, 9)
    painter.end()
    return QIcon(image)


class CelestialHeader(QWidget):
    """One quiet reveal on opening; no timer runs while the menu is closed."""
    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName('menu-header')
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.starlight = .65
        self.reveal = QVariantAnimation(self)
        self.reveal.setStartValue(.25)
        self.reveal.setEndValue(.8)
        self.reveal.setDuration(1800)
        self.reveal.valueChanged.connect(self.set_starlight)

    def set_starlight(self, value):
        self.starlight = float(value)
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        # Respect Windows' animation accessibility preference.
        animate = False
        try:
            import ctypes
            enabled = ctypes.c_int(0)
            animate = bool(ctypes.windll.user32.SystemParametersInfoW(
                0x1042, 0, ctypes.byref(enabled), 0) and enabled.value)
        except (AttributeError, OSError):
            pass
        if animate:
            self.reveal.start()

    def hideEvent(self, event):
        self.reveal.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width()-46, 8)
        painter.setPen(QPen(QColor('#d4e1eb'), .8))
        painter.drawLine(QPointF(8, 16), QPointF(28, 38))
        painter.drawLine(QPointF(28, 38), QPointF(14, 70))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#92b4cd'))
        for x, y, r in ((8,16,1.6),(28,38,1.2),(14,70,1.5),(32,80,.9)):
            painter.drawEllipse(QPointF(x,y),r,r)
        painter.setOpacity(self.starlight)
        painter.translate(28,38)
        path = QPainterPath()
        path.moveTo(0,-7)
        for x,y in ((1.6,-1.6),(7,0),(1.6,1.6),(0,7),(-1.6,1.6),(-7,0),(-1.6,-1.6)):
            path.lineTo(x,y)
        path.closeSubpath()
        painter.setBrush(QColor('#638fae'))
        painter.drawPath(path)
        painter.end()


class CompanionMenu(QMenu):
    def __init__(self, parent, avatar):
        super().__init__(parent)
        self.setObjectName('yuki-menu')
        self.setFont(QFont('Microsoft YaHei UI', 10))
        self.setMinimumWidth(270)
        self.setStyleSheet('''
            QMenu { background: #fcfdff; color: #253b4e; border: 1px solid #d4e0e9;
                    border-radius: 9px; padding: 7px; }
            QMenu::item { padding: 11px 22px 11px 14px; border-radius: 5px; }
            QMenu::item:selected { background: #eaf3f8; color: #306f96; }
            QMenu::item:disabled { color: #96a5af; }
            QMenu::separator { height: 1px; background: #e2e9ef; margin: 7px 10px; }
            QMenu::indicator { width: 14px; height: 14px; margin-left: 10px;
                               border: 1px solid #b9cad7; border-radius: 3px; }
            QMenu::indicator:checked { background: #6293b4; border-color: #6293b4; }
            QWidget#menu-header { background: transparent; }
            QLabel { background: transparent; color: #253b4e; border: none; }
        ''')
        header = CelestialHeader(self)
        self.celestial_header = header
        row = QHBoxLayout(header)
        row.setContentsMargins(12, 10, 46, 16)
        row.setSpacing(13)
        portrait = QLabel()
        portrait.setPixmap(avatar.pixmap(QSize(44, 52)))
        row.addWidget(portrait)
        copy = QVBoxLayout()
        copy.setSpacing(4)
        name = QLabel('yuki.')
        name.setStyleSheet('font: 24px "Segoe UI"; color: #306f96;')
        self.status = QLabel()
        self.status.setStyleSheet('font-size: 11px; color: #657887;')
        copy.addWidget(name)
        copy.addWidget(self.status)
        self.routine = QLabel()
        self.routine.setStyleSheet('font-size: 10px; color: #8196a5;')
        copy.addWidget(self.routine)
        row.addLayout(copy, 1)
        action = QWidgetAction(self)
        action.setDefaultWidget(header)
        action.setEnabled(False)
        self.addAction(action)

    def command(self, name, label, callback, icon=None, checkable=False):
        action = self.addAction(menu_icon(icon), label) if icon else self.addAction(label)
        action.setObjectName(name)
        action.setCheckable(checkable)
        action.triggered.connect(callback)
        return action

    def quick_chat(self, controller):
        self.chat_controller = controller
        # QMenu does not enable IME by default. Windows routes composition
        # through the popup window as well as its focused editor.
        self.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        composer = QWidget(self)
        layout = QVBoxLayout(composer)
        layout.setContentsMargins(10, 6, 10, 9)
        layout.setSpacing(7)
        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.chat_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.chat_input.setAccessibleName('与 yuki 快捷聊天')
        self.chat_input.setPlaceholderText('想对 yuki 说些什么？')
        self.chat_input.setMaxLength(2000)
        self.chat_input.setText(controller.quick_draft)
        self.chat_input.setStyleSheet('QLineEdit { background:#f0f6fa; color:#29495f; border:1px solid #dae6ee; border-radius:7px; padding:9px; selection-background-color:#c6dfef; } QLineEdit:focus { border-color:#83abc6; }')
        self.chat_input.textEdited.connect(lambda text: setattr(controller, 'quick_draft', text))
        self.chat_send = QToolButton()
        self.chat_send.setText('↑')
        self.chat_send.setAccessibleName('发送给 yuki')
        self.chat_send.setToolTip('发送 · Enter')
        self.chat_send.setStyleSheet('QToolButton { background:#e7f1f8; color:#39749c; border:1px solid #c9dce9; border-radius:7px; font-size:18px; padding:5px 9px; } QToolButton:hover { background:#d6e9f5; } QToolButton:disabled { color:#9baeba; }')
        row.addWidget(self.chat_input, 1)
        row.addWidget(self.chat_send)
        layout.addLayout(row)
        self.chat_hint = QLabel('Enter 发送 · Esc 收起')
        self.chat_hint.setStyleSheet('color:#8196a5; font-size:10px;')
        layout.addWidget(self.chat_hint)
        action = QWidgetAction(self)
        action.setDefaultWidget(composer)
        self.addAction(action)
        self.aboutToShow.connect(lambda: QTimer.singleShot(0, self.focus_chat))

        def submit():
            text = self.chat_input.text().strip()
            if not text or controller.quick_pending:
                return
            controller.quick_draft = text
            if controller.quick_chat_send(text):
                self.chat_input.clear()
                controller.quick_draft = ''
                self.close()

        self.chat_input.returnPressed.connect(submit)
        self.chat_send.clicked.connect(submit)
        controller.changed.connect(self.refresh_chat)

    def focus_chat(self):
        if self.isVisible() and self.chat_input.isEnabled():
            self.activateWindow()
            self.chat_input.setFocus(Qt.FocusReason.PopupFocusReason)

    def refresh_chat(self):
        self.update_chat(self.chat_controller)

    def update_chat(self, controller):
        if not hasattr(self, 'chat_input'):
            return
        busy = bool(controller.quick_pending)
        was_busy = not self.chat_input.isEnabled()
        self.chat_input.setEnabled(not busy)
        self.chat_send.setEnabled(not busy)
        self.chat_hint.setText('yuki 正在回复…' if busy else 'Enter 发送 · Esc 收起')
        if was_busy and not busy:
            self.chat_input.setText(controller.quick_draft)
