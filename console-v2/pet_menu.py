"""Shared, keyboard-accessible menu for the pet and the system tray."""
from html import escape
from pet_quick_tools import QuickToolsPane
from PySide6.QtCore import QSize, Qt, QTimer, QVariantAnimation, QPointF, QRectF
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QFont, QIcon, QPainter, QPen, QPixmap, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMenu, QToolButton, QVBoxLayout, QWidget, QWidgetAction, QTextBrowser, QTabBar, QStackedWidget, QScrollArea, QFrame, QSizePolicy


def menu_icon(kind, color='#527b97'):
    image = QPixmap(20, 20)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine,
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
    elif kind == 'translate':
        painter.drawRoundedRect(3, 3, 14, 14, 3, 3)
        painter.setFont(QFont('Segoe UI', 8))
        painter.drawText(QRectF(4, 3, 7, 14), Qt.AlignmentFlag.AlignCenter, 'A')
        painter.setFont(QFont('Microsoft YaHei UI', 7))
        painter.drawText(QRectF(9, 3, 7, 14), Qt.AlignmentFlag.AlignCenter, '文')
    elif kind == 'climb':
        painter.drawLine(4, 16, 16, 4)
        painter.drawLine(8, 4, 16, 4)
        painter.drawLine(16, 4, 16, 12)
        painter.drawLine(3, 17, 9, 17)
    elif kind == 'send':
        painter.drawLine(10, 16, 10, 4)
        painter.drawLine(5, 9, 10, 4)
        painter.drawLine(10, 4, 15, 9)
    painter.end()
    return QIcon(image)


class CelestialHeader(QWidget):
    """One quiet reveal on opening; no timer runs while the menu is closed."""
    def __init__(self, parent):
        super().__init__(parent)
        self.menu = parent
        self.setObjectName('menu-header')
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._drag_origin = None
        self._menu_origin = None
        self.starlight = .65
        self.line_color = QColor('#c5d8e4')
        self.star_color = QColor('#7fa8c2')
        self.accent_color = QColor('#638fae')
        self.reveal = QVariantAnimation(self)
        self.reveal.setStartValue(.25)
        self.reveal.setEndValue(.8)
        self.reveal.setDuration(1800)
        self.reveal.valueChanged.connect(self.set_starlight)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint()
            self._menu_origin = self.menu.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.menu.move_menu_to(event.globalPosition().toPoint(), self._drag_origin, self._menu_origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_origin is not None:
            self._drag_origin = None
            self._menu_origin = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def set_starlight(self, value):
        self.starlight = float(value)
        self.update()

    def set_palette(self, line, star, accent):
        self.line_color = QColor(line)
        self.star_color = QColor(star)
        self.accent_color = QColor(accent)
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
        if animate and not getattr(self, 'reduced', False):
            self.reveal.start()

    def hideEvent(self, event):
        self.reveal.stop()
        super().hideEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.translate(self.width()-46, 8)
        painter.setPen(QPen(self.line_color, .8))
        painter.drawLine(QPointF(8, 16), QPointF(28, 38))
        painter.drawLine(QPointF(28, 38), QPointF(14, 70))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self.star_color)
        for x, y, r in ((8,16,1.6),(28,38,1.2),(14,70,1.5),(32,80,.9)):
            painter.drawEllipse(QPointF(x,y),r,r)
        painter.setOpacity(self.starlight)
        painter.translate(28,38)
        path = QPainterPath()
        path.moveTo(0,-7)
        for x,y in ((1.6,-1.6),(7,0),(1.6,1.6),(0,7),(-1.6,1.6),(-7,0),(-1.6,-1.6)):
            path.lineTo(x,y)
        path.closeSubpath()
        painter.setBrush(self.accent_color)
        painter.drawPath(path)
        painter.setOpacity(1)
        painter.setPen(QPen(self.line_color, .7))
        painter.drawLine(12, self.height()-1, self.width()-12, self.height()-1)
        painter.end()


class MenuResizeHandle(QWidget):
    """Small, unobtrusive resize affordance matching the translation popup."""
    def __init__(self, menu):
        super().__init__(menu)
        self.menu = menu
        self.setObjectName('menu-resize-handle')
        self.setFixedSize(19, 19)
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self._origin = None
        self._size = None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = event.globalPosition().toPoint()
            self._size = self.menu.size()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            delta = event.globalPosition().toPoint() - self._origin
            self.menu.resize_from_handle(self._size.width() + delta.x(), self._size.height() + delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._origin = self._size = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(getattr(self.menu, '_palette', {}).get('muted', '#8196a5'))
        color.setAlpha(165)
        painter.setPen(QPen(color, 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        for offset in (5, 9, 13):
            painter.drawLine(self.width()-offset, self.height()-2, self.width()-2, self.height()-offset)
        painter.end()


class CompanionMenu(QMenu):
    _last_size = QSize(328, 0)
    _user_resized = False

    def __init__(self, parent, avatar):
        super().__init__(parent)
        self.setObjectName('yuki-menu')
        self.setFont(QFont('Microsoft YaHei UI', 10))
        self.setMinimumSize(280, 160)
        self._applying_size = False
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
        for child in header.findChildren(QLabel):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row = QHBoxLayout(header)
        row.setContentsMargins(14, 10, 44, 14)
        row.setSpacing(12)
        copy = QVBoxLayout()
        copy.setSpacing(3)
        name = QLabel('yuki')
        name.setObjectName('wordmark')
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
        self.addAction(action)
        self.apply_theme('mist')

    def keyPressEvent(self, event):
        # The popup menu also treats Enter as "activate and close". While the
        # inline clock is being edited, consume it as an input commit instead.
        clock = getattr(self, 'clock_editor', None)
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and clock is not None and clock.hasFocus() and not clock.isReadOnly()):
            clock.commitRequested.emit()
            event.accept()
            return
        custom_minutes = getattr(self, 'custom_minutes_editor', None)
        if (event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and custom_minutes is not None and custom_minutes.hasFocus()):
            custom_minutes.commitRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def apply_theme(self, theme):
        reduced = bool(getattr(getattr(self, 'chat_controller', None), 'ui_reduced', False))
        if getattr(self, '_theme_key', None) == (theme, reduced, hasattr(self, 'chat_input')):
            return
        self._theme_key = (theme, reduced, hasattr(self, 'chat_input'))
        palettes = {
            'light': dict(bg='#fbfdfe', fg='#14232b', muted='#5e717c', hover='#edf3f7',
                          border='#d9e4ea', accent='#2f6f8f', inset='#f1f6f9',
                          line='#cddfe9', star='#7fa8c2'),
            'mist': dict(bg='#f2f6f8', fg='#15242c', muted='#5b6f7a', hover='#e5edf1',
                         border='#cfdde4', accent='#346f8b', inset='#eaf1f4',
                         line='#c3d6e1', star='#6f9bb5'),
            'dark': dict(bg='#101820', fg='#e8eff4', muted='#97a9b5', hover='#182630',
                         border='#2a3a45', accent='#9fc9dc', inset='#15232d',
                         line='#2f4654', star='#6f9bb5'),
        }
        p = palettes.get(theme, palettes['mist'])
        self.setStyleSheet(f'''
            QMenu {{ background:{p['bg']}; color:{p['fg']}; border:1px solid {p['border']};
                    border-radius:16px; padding:9px; font-size:13px; }}
            QMenu::item {{ padding:10px 20px 10px 12px; border-radius:8px; margin:1px 0; }}
            QMenu::item:selected {{ background:{p['hover']}; color:{p['fg']}; }}
            QMenu::item:disabled {{ color:{p['muted']}; }}
            QMenu::separator {{ height:1px; background:{p['border']}; margin:6px 10px; }}
            QMenu::indicator {{ width:13px; height:13px; margin-left:12px;
                               border:1px solid {p['border']}; border-radius:3px; }}
            QMenu::indicator:checked {{ background:{p['accent']}; border-color:{p['accent']}; }}
            QWidget#menu-header, QLabel {{ background:transparent; color:{p['fg']}; border:none; }}
            QLabel#wordmark {{ font:italic 27px 'Georgia'; color:{p['accent']}; }}
            QTabBar {{ background:{p['inset']}; border-radius:9px; padding:3px; }}
            QTabBar::tab {{ color:{p['muted']}; padding:7px 10px; margin:0 1px;
                           border:0; border-radius:7px; font-size:12px; }}
            QTabBar::tab:hover {{ color:{p['fg']}; background:{p['hover']}; }}
            QTabBar::tab:selected {{ color:{p['accent']}; background:{p['bg']}; font-weight:600; }}
            QTextBrowser {{ background:{p['inset']}; color:{p['fg']}; border:1px solid {p['border']};
                           border-radius:10px; padding:8px; font-size:12px; }}
            QLineEdit {{ background:{p['bg']}; color:{p['fg']}; border:1px solid {p['border']};
                        border-radius:10px; padding:10px 12px; selection-background-color:{p['accent']}; }}
            QLineEdit:focus {{ border-color:{p['accent']}; }}
            QToolButton {{ background:{p['inset']}; color:{p['accent']}; border:1px solid {p['border']};
                          border-radius:10px; padding:7px 10px; font-size:12px; }}
            QToolButton:hover {{ background:{p['hover']}; }}
            QToolButton:focus {{ border-color:{p['accent']}; }}
            QToolButton:pressed {{ background:{p['border']}; }}
            QToolButton:disabled {{ color:{p['muted']}; }}
            QPushButton {{ background:{p['inset']}; color:{p['fg']}; border:1px solid {p['border']};
                          border-radius:8px; padding:6px 10px; font-size:11px; }}
            QPushButton:hover {{ background:{p['hover']}; }}
            QComboBox {{ background:{p['inset']}; color:{p['fg']}; border:1px solid {p['border']};
                        border-radius:8px; padding:6px; }}
            QListWidget {{ background:transparent; color:{p['fg']}; border:none; font-size:12px; }}
            QListWidget::item {{ padding:8px 6px; border-bottom:1px solid {p['border']}; border-radius:6px; }}
            QListWidget::item:hover {{ background:{p['hover']}; }}
            QListWidget::item:selected {{ background:{p['hover']}; color:{p['fg']}; }}
            QLabel#muted {{ color:{p['muted']}; font-size:11px; }}
            QLineEdit#timer-reading {{ font:34px 'Segoe UI'; color:{p['accent']}; background:transparent;
                                      border:1px solid transparent; padding:2px; selection-background-color:{p['accent']}; }}
            QLineEdit#timer-reading:focus {{ border-color:{p['border']}; border-radius:8px; }}
            QLabel#tool-feedback {{ color:{p['muted']}; font-size:11px; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
        ''')
        self.setStyleSheet(self.styleSheet()+f'''
            QScrollBar:vertical {{ background:transparent; width:6px; margin:0; }}
            QScrollBar::handle:vertical {{ background:{p['border']}; border-radius:3px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        ''')
        self._palette = p
        self._icon_color = p['accent']
        icon_kinds = {'console': 'console', 'exit': 'exit', 'translation': 'translate'}
        for action in self.actions():
            kind = icon_kinds.get(action.objectName())
            if kind:
                action.setIcon(menu_icon(kind, p['accent']))
        self.status.setStyleSheet(f"font-size:12px;color:{p['muted']};letter-spacing:.02em;")
        self.routine.setStyleSheet(f"font-size:10.5px;color:{p['muted']};letter-spacing:.03em;")
        self.celestial_header.set_palette(p['line'], p['star'], p['accent'])
        self.celestial_header.reveal.setDuration(900)
        self.celestial_header.reduced = reduced
        if hasattr(self, 'chat_input'):
            self.chat_input.setStyleSheet('')
            self.chat_send.setStyleSheet('')
            self.chat_send.setIcon(menu_icon('send', p['accent']))
            self.chat_hint.setStyleSheet(f"font-size:10.5px;color:{p['muted']};letter-spacing:.02em;")
            self.chat_reply.setStyleSheet('')

    def command(self, name, label, callback, icon=None, checkable=False):
        action = self.addAction(menu_icon(icon, getattr(self, '_icon_color', '#527b97')), label) if icon else self.addAction(label)
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
        self.composer = composer
        composer.setMinimumWidth(260)
        layout = QVBoxLayout(composer)
        layout.setContentsMargins(10, 6, 10, 9)
        layout.setSpacing(7)
        composer.setFixedHeight(300)
        self.tabs = QTabBar()
        self.tabs.setDrawBase(False)
        self.tabs.setExpanding(True)
        for title in ('对话', '剪贴板', '时间', '待办'): self.tabs.addTab(title)
        layout.addWidget(self.tabs)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)
        chat_page = QWidget()
        chat_layout = QVBoxLayout(chat_page)
        chat_layout.setContentsMargins(0, 0, 0, 0)
        chat_layout.setSpacing(6)
        self.chat_reply = QTextBrowser()
        self.chat_reply.setAccessibleName('与 yuki 的近期对话，滚轮回看')
        self.chat_reply.setOpenExternalLinks(False)
        self.chat_reply.setOpenLinks(False)
        self.chat_reply.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        chat_layout.addWidget(self.chat_reply, 1)
        self.pages.addWidget(chat_page)
        self.tool_panes = []
        for kind in ('clipboard', 'focus', 'todos'):
            pane = QuickToolsPane(kind)
            if kind == 'focus':
                self.clock_editor = pane.clock
                self.custom_minutes_editor = pane.custom_minutes
            pane.request.connect(controller.quick_tool_send)
            self.tool_panes.append(pane)
            scroll = QScrollArea()
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setAccessibleName('快捷工具滚动区域')
            pane.setMinimumHeight(220)
            scroll.setWidget(pane)
            self.pages.addWidget(scroll)
        self.tabs.currentChanged.connect(self.pages.setCurrentIndex)
        self.tabs.currentChanged.connect(lambda _: controller.quick_tool_send('snapshot'))
        row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setAttribute(Qt.WidgetAttribute.WA_InputMethodEnabled, True)
        self.chat_input.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.chat_input.setAccessibleName('与 yuki 快捷聊天')
        self.chat_input.setPlaceholderText('想对 yuki 说些什么？')
        self.chat_input.setMinimumWidth(0)
        self.chat_input.setMaxLength(2000)
        self.chat_input.setMinimumHeight(38)
        self.chat_input.setText(controller.quick_draft)
        self.chat_input.setStyleSheet('QLineEdit { background:#f0f6fa; color:#29495f; border:1px solid #dae6ee; border-radius:7px; padding:9px; selection-background-color:#c6dfef; } QLineEdit:focus { border-color:#83abc6; }')
        self.chat_input.textEdited.connect(lambda text: setattr(controller, 'quick_draft', text))
        self.chat_send = QToolButton()
        self.chat_send.setMinimumSize(38, 38)
        self.chat_send.setIcon(menu_icon('send'))
        self.chat_send.setIconSize(QSize(20, 20))
        self.chat_send.setAccessibleName('发送给 yuki')
        self.chat_send.setToolTip('发送 · Enter')
        self.chat_send.setStyleSheet('QToolButton { background:#e7f1f8; color:#39749c; border:1px solid #c9dce9; border-radius:7px; font-size:18px; padding:5px 9px; } QToolButton:hover { background:#d6e9f5; } QToolButton:disabled { color:#9baeba; }')
        row.addWidget(self.chat_input, 1)
        row.addWidget(self.chat_send)
        chat_layout.addLayout(row)
        self.chat_hint = QLabel('Enter 发送 · Esc 收起')
        self.chat_hint.setStyleSheet('color:#8196a5; font-size:10px;')
        chat_layout.addWidget(self.chat_hint)
        action = QWidgetAction(self)
        action.setDefaultWidget(composer)
        self.chat_action = action
        self.addAction(action)
        self.aboutToShow.connect(self.fit_available_height)
        self.aboutToShow.connect(lambda: QTimer.singleShot(0, self.focus_chat))
        self.aboutToShow.connect(lambda: controller.quick_tool_send('snapshot'))
        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(2500)
        self.refresh_timer.timeout.connect(lambda: controller.quick_tool_send('snapshot') if self.tabs.currentIndex() else None)
        self.aboutToShow.connect(self.refresh_timer.start)
        self.aboutToHide.connect(self.refresh_timer.stop)

        def submit():
            text = self.chat_input.text().strip()
            if not text or controller.quick_pending:
                return
            controller.quick_draft = text
            if controller.quick_chat_send(text):
                self.chat_input.clear()
                controller.quick_draft = ''
                self.update_chat(controller)

        self.chat_input.returnPressed.connect(submit)
        self.chat_send.clicked.connect(submit)
        controller.changed.connect(self.refresh_chat)

        self.resize_handle = MenuResizeHandle(self)
        grip_row = QWidget(self)
        grip_row.setMinimumWidth(260)
        grip_row.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grip_layout = QHBoxLayout(grip_row)
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch(1)
        grip_layout.addWidget(self.resize_handle)
        grip_action = QWidgetAction(self)
        grip_action.setDefaultWidget(grip_row)
        grip_action.setEnabled(True)
        self.addAction(grip_action)
        self.aboutToShow.connect(self.restore_menu_size)
        self.resize_handle_action = grip_action

    def restore_menu_size(self):
        self._applying_size = True
        saved = CompanionMenu._last_size
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
        area = screen.availableGeometry()
        width = min(area.width(), max(self.minimumWidth(), saved.width()))
        height = min(area.height(), max(self.minimumHeight(), saved.height() if CompanionMenu._user_resized else self.height()))
        self.resize(width, height)
        self._applying_size = False
        QTimer.singleShot(0, self.sync_resizable_content)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'composer'):
            return
        if CompanionMenu._user_resized and not self._applying_size:
            CompanionMenu._last_size = QSize(self.width(), self.height())
        self.sync_resizable_content()

    def sync_resizable_content(self):
        if not hasattr(self, 'composer'):
            return
        self.composer.setFixedWidth(max(260, self.width()-20))
        if getattr(self, '_menu_chrome_height', 0):
            self.composer.setFixedHeight(max(150, self.height()-self._menu_chrome_height))

    def resize_from_handle(self, width, height):
        screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
        area = screen.availableGeometry()
        width = max(self.minimumWidth(), min(int(width), area.right()-self.x()+1))
        height = max(self.minimumHeight(), min(int(height), area.bottom()-self.y()+1))
        self.resize(width, height)
        CompanionMenu._user_resized = True
        CompanionMenu._last_size = QSize(self.width(), self.height())

    def move_menu_to(self, point, origin, menu_origin):
        delta = point-origin
        target = menu_origin+delta
        screen = QGuiApplication.screenAt(point) or self.screen()
        area = screen.availableGeometry()
        x = max(area.left()-self.width()+64, min(target.x(), area.right()-63))
        y = max(area.top(), min(target.y(), area.bottom()-39))
        self.move(x, y)

    def fit_available_height(self, available_height=None):
        # Keep tabs and menu commands reachable; only the tool body scrolls.
        if available_height is None:
            screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
            available_height = screen.availableGeometry().height()
        self.ensurePolished()
        chrome = getattr(self, '_menu_chrome_height', max(0, self.sizeHint().height()-self.composer.height()))
        self._menu_chrome_height = chrome
        height = max(180, min(300, available_height-chrome-20))
        if not CompanionMenu._user_resized:
            self.composer.setFixedHeight(height)
            self.setMinimumHeight(max(180, chrome+150))
            self.resize(self.width(), chrome+height)
            CompanionMenu._last_size = QSize(self.width(), chrome+height)
        self._menu_chrome_height = chrome
        self.sync_resizable_content()

    def focus_chat(self):
        if self.isVisible() and self.tabs.currentIndex() == 0 and self.chat_input.isEnabled():
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
        history = list(getattr(controller, 'quick_history', []))[-60:]
        reply = getattr(controller, 'quick_reply', '')
        if reply and (not history or (busy and history[-1].get('text') != reply)):
            history.append({'role':'assistant', 'text':reply})
        palette = getattr(self, '_palette', {})
        fg = palette.get('fg', '#15242c')
        muted = palette.get('muted', '#5b6f7a')
        accent = palette.get('accent', '#346f8b')
        signature = ((theme if (theme := getattr(self, '_theme_key', ('mist',))[0]) else 'mist'),
                     [(entry.get('role'), entry.get('text')) for entry in history])
        if signature != getattr(self, '_chat_signature', None):
            self._chat_signature = signature
            scroll = self.chat_reply.verticalScrollBar()
            old = scroll.value()
            follow = scroll.maximum()-old < 20
            blocks = []
            for entry in history:
                who = '你' if entry.get('role') == 'user' else 'yuki'
                who_color = muted if entry.get('role') == 'user' else accent
                content = escape(str(entry.get('text', ''))).replace('\n','<br>')
                blocks.append(f'<p style="margin:4px 0 12px;line-height:1.7"><span style="font-size:10.5px;letter-spacing:.08em;color:{who_color}">{who}</span><br>{content}</p>')
            empty = ('<div style="text-align:center;padding:36px 8px 8px">'
                     f'<p style="margin:0 0 7px;font-size:15px;color:{fg}">和 yuki 说句话吧。</p>'
                     f'<p style="margin:0;font-size:11.5px;color:{muted}">近期对话可用滚轮回看。</p></div>')
            self.chat_reply.setHtml(''.join(blocks) or empty)
            scroll.setValue(scroll.maximum() if follow else min(old, scroll.maximum()))
        for pane in self.tool_panes:
            pane.refresh(getattr(controller, 'quick_tools', {}))
        if was_busy and not busy:
            self.chat_input.setText(controller.quick_draft)
