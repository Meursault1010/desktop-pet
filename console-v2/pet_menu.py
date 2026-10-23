"""Shared, keyboard-accessible menu for the pet and the system tray."""
from html import escape
from pet_quick_tools import QuickToolsPane
from PySide6.QtCore import QSize, Qt, QTimer, QVariantAnimation, QPointF
from PySide6.QtGui import QColor, QCursor, QGuiApplication, QFont, QIcon, QPainter, QPen, QPixmap, QPainterPath
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMenu, QToolButton, QVBoxLayout, QWidget, QWidgetAction, QTextBrowser, QTabBar, QStackedWidget, QScrollArea, QFrame


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
        self.setFixedWidth(328)
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
        copy = QVBoxLayout()
        copy.setSpacing(4)
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
        action.setEnabled(False)
        self.addAction(action)
        self.apply_theme('mist')

    def apply_theme(self, theme):
        reduced = bool(getattr(getattr(self, 'chat_controller', None), 'ui_reduced', False))
        if getattr(self, '_theme_key', None) == (theme, reduced, hasattr(self, 'chat_input')):
            return
        self._theme_key = (theme, reduced, hasattr(self, 'chat_input'))
        palettes = {
            'light': ('#f9fbfd', '#20394e', '#526a7d', '#eaf0f5', '#d3dfe8', '#2e6388'),
            'mist': ('#e9eff4', '#243c50', '#50667a', '#dce6ee', '#bdcedc', '#295d84'),
            'dark': ('#172431', '#e6eef5', '#a7bbc9', '#233849', '#3b5367', '#a6cbea'),
        }
        bg, fg, muted, hover, border, accent = palettes.get(theme, palettes['mist'])
        self.setStyleSheet(f'''
            QMenu {{ background:{bg}; color:{fg}; border:1px solid {border}; border-radius:12px; padding:8px; }}
            QMenu::item {{ padding:11px 24px 11px 14px; border-radius:6px; }}
            QMenu::item:selected {{ background:{hover}; }}
            QMenu::separator {{ height:1px; background:{border}; margin:7px 12px; }}
            QMenu::indicator {{ width:13px; height:13px; margin-left:12px; border:1px solid {border}; border-radius:3px; }}
            QMenu::indicator:checked {{ background:{accent}; }}
            QWidget#menu-header, QLabel {{ background:transparent; color:{fg}; border:none; }}
            QLabel#wordmark {{ font:italic 26px 'Georgia'; color:{accent}; }}
            QLineEdit {{ background:{hover}; color:{fg}; border:1px solid {border}; border-radius:8px; padding:10px; selection-background-color:{accent}; }}
            QLineEdit:focus {{ border-color:{accent}; }}
            QToolButton {{ background:{hover}; color:{accent}; border:1px solid {border}; border-radius:8px; padding:7px 10px; font-size:12px; }}
            QToolButton:hover {{ background:{border}; }}
            QToolButton:disabled {{ color:{muted}; }}
        ''')
        self.setStyleSheet(self.styleSheet()+f"""
            QTabBar::tab {{ color:{muted}; padding:8px 10px; border-bottom:2px solid transparent; }}
            QTabBar::tab:selected {{ color:{accent}; border-bottom-color:{accent}; }}
            QScrollArea, QScrollArea > QWidget > QWidget {{ background:transparent; border:none; }}
            QTextBrowser, QListWidget {{ background:transparent; color:{fg}; border:none; font-size:12px; }}
            QListWidget::item {{ padding:9px 5px; border-bottom:1px solid {border}; }}
            QListWidget::indicator {{ width:12px; height:12px; border:1px solid {border}; border-radius:3px; background:transparent; }}
            QListWidget::indicator:checked {{ background:{accent}; }}
            QListWidget::item:selected {{ background:{hover}; color:{fg}; }}
            QLabel#muted {{ color:{muted}; font-size:11px; }}
            QLabel#timer-reading {{ font:36px 'Segoe UI'; color:{accent}; }}
            QLabel#tool-feedback {{ color:{muted}; font-size:11px; }}
            QComboBox {{ background:{hover}; color:{fg}; border:1px solid {border}; border-radius:6px; padding:5px; }}
            QScrollBar:vertical {{ background:transparent; width:5px; margin:0; }}
            QScrollBar::handle:vertical {{ background:{border}; border-radius:2px; min-height:24px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self.status.setStyleSheet(f'font-size:12px;color:{muted};')
        self.routine.setStyleSheet(f'font-size:11px;color:{muted};')
        self.celestial_header.reveal.setDuration(900)
        self.celestial_header.reduced = reduced
        if hasattr(self, 'chat_input'):
            self.chat_input.setStyleSheet('')
            self.chat_send.setStyleSheet('')
            self.chat_hint.setStyleSheet(f'font-size:10px;color:{muted};')
            self.chat_reply.setStyleSheet(f'font-size:12px;color:{fg};padding:8px 2px;')

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
        self.composer = composer
        composer.setFixedWidth(308)
        layout = QVBoxLayout(composer)
        layout.setContentsMargins(10, 6, 10, 9)
        layout.setSpacing(7)
        composer.setFixedHeight(300)
        self.tabs = QTabBar()
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

    def fit_available_height(self, available_height=None):
        # Keep tabs and menu commands reachable; only the tool body scrolls.
        if available_height is None:
            screen = QGuiApplication.screenAt(QCursor.pos()) or self.screen()
            available_height = screen.availableGeometry().height()
        self.ensurePolished()
        chrome = getattr(self, '_menu_chrome_height', max(0, self.sizeHint().height()-self.composer.height()))
        self._menu_chrome_height = chrome
        height = max(180, min(300, available_height-chrome-20))
        self.composer.setFixedHeight(height)
        self.setFixedHeight(chrome+height)

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
        signature = [(entry.get('role'), entry.get('text')) for entry in history]
        if signature != getattr(self, '_chat_signature', None):
            self._chat_signature = signature
            scroll = self.chat_reply.verticalScrollBar()
            old = scroll.value()
            follow = scroll.maximum()-old < 20
            blocks = []
            for entry in history:
                who = '你' if entry.get('role') == 'user' else 'yuki'
                content = escape(str(entry.get('text', ''))).replace('\n','<br>')
                blocks.append(f'<p style="margin:4px 0 12px"><b>{who}</b><br>{content}</p>')
            self.chat_reply.setHtml(''.join(blocks) or '<p>和 yuki 说句话吧。<br>近期对话可用滚轮回看。</p>')
            scroll.setValue(scroll.maximum() if follow else min(old, scroll.maximum()))
        for pane in self.tool_panes:
            pane.refresh(getattr(controller, 'quick_tools', {}))
        if was_busy and not busy:
            self.chat_input.setText(controller.quick_draft)
