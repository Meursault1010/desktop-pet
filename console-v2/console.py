"""用户可见的控制台；所有操作交给共用控制层处理。"""
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QScrollArea, QSlider,
    QVBoxLayout, QWidget,
)

from settings_model import ACTIVITIES, LIMITS


class ControlWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.sliders = {}
        self.checks = {}
        self.setWindowTitle('yuki · 控制台')
        self.setMinimumSize(480, 430)
        self.resize(600, 760)
        self.setWindowIcon(controller.icon)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)
        title = QLabel('yuki的桌面小屋')
        title.setObjectName('title')
        layout.addWidget(title)
        caption = QLabel('陪你工作，也给你留一点安静。')
        caption.setObjectName('caption')
        layout.addWidget(caption)

        status_group = QGroupBox('宠物状态')
        status_layout = QVBoxLayout(status_group)
        self.status_label = QLabel()
        self.status_label.setObjectName('status')
        status_layout.addWidget(self.status_label)
        buttons = QHBoxLayout()
        self.visibility_button = QPushButton()
        self.visibility_button.clicked.connect(controller.toggle_visibility)
        self.pause_button = QPushButton()
        self.pause_button.clicked.connect(controller.toggle_pause)
        self.home_button = QPushButton('回到桌面底部')
        self.home_button.clicked.connect(lambda: controller.pet.go_home())
        buttons.addWidget(self.visibility_button)
        buttons.addWidget(self.pause_button)
        buttons.addWidget(self.home_button)
        status_layout.addLayout(buttons)
        self.behavior_hint = QLabel()
        self.behavior_hint.setWordWrap(True)
        status_layout.addWidget(self.behavior_hint)
        layout.addWidget(status_group)

        appearance = QGroupBox('外观')
        appearance_form = QFormLayout(appearance)
        appearance_form.addRow('当前角色', QLabel('yuki · 白发蓝裙角色'))
        self.add_slider(appearance_form, '宠物大小', 'size', '%')
        self.add_slider(appearance_form, '不透明度', 'opacity', '%')
        opacity_hint = QLabel('设为 0 会直接隐藏宠物；再次显示时恢复上次的不透明度。')
        opacity_hint.setWordWrap(True)
        opacity_hint.setObjectName('caption')
        appearance_form.addRow(opacity_hint)
        self.add_check(appearance_form, '始终置顶', 'always_on_top')
        layout.addWidget(appearance)

        behavior = QGroupBox('行为')
        behavior_form = QFormLayout(behavior)
        self.add_slider(behavior_form, '移动速度', 'speed', ' 像素/秒')
        self.activity = QComboBox()
        self.activity.addItems(ACTIVITIES)
        self.activity.currentTextChanged.connect(
            lambda value: controller.set_preference('activity', value))
        behavior_form.addRow('活动频率', self.activity)
        self.add_check(behavior_form, '自主巡逻与生活', 'random_movement')
        self.add_check(behavior_form, '点击时显示问候气泡', 'greeting')
        self.add_check(behavior_form, '安静模式', 'quiet')
        self.add_check(behavior_form, '拖放即时吸附', 'auto_snap')
        quiet_hint = QLabel('安静模式临时关闭自主移动和问候气泡，关闭后恢复原设置。')
        quiet_hint.setWordWrap(True)
        quiet_hint.setObjectName('caption')
        behavior_form.addRow(quiet_hint)
        layout.addWidget(behavior)

        actions = QGroupBox('动作测试')
        action_layout = QHBoxLayout(actions)
        self.jump_button = QPushButton('跳一下')
        self.jump_button.clicked.connect(controller.pet.animator.jump)
        action_layout.addWidget(self.jump_button)
        hint = QLabel('暂停时也可以跳跃；隐藏时请先显示宠物。')
        hint.setWordWrap(True)
        action_layout.addWidget(hint, 1)
        layout.addWidget(actions)

        footer_buttons = QHBoxLayout()
        reset = QPushButton('恢复默认设置')
        reset.clicked.connect(self.confirm_reset)
        footer_buttons.addWidget(reset)
        footer_buttons.addStretch()
        quit_button = QPushButton('退出yuki')
        quit_button.clicked.connect(controller.quit)
        footer_buttons.addWidget(quit_button)
        layout.addLayout(footer_buttons)
        self.save_label = QLabel()
        self.save_label.setWordWrap(True)
        self.save_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.save_label.setObjectName('caption')
        layout.addWidget(self.save_label)
        self.close_hint = QLabel()
        self.close_hint.setWordWrap(True)
        self.close_hint.setObjectName('caption')
        layout.addWidget(self.close_hint)
        layout.addStretch()
        scroll.setWidget(content)
        self.setCentralWidget(scroll)
        self.setStyleSheet('''
            QMainWindow, QScrollArea, QScrollArea > QWidget > QWidget { background: #faf7f2; }
            QWidget { color: #463b32; font-family: "Microsoft YaHei UI"; font-size: 13px; }
            QLabel#title { font-size: 24px; font-weight: 600; }
            QLabel#caption { color: #786c60; font-size: 12px; }
            QLabel#status { color: #9b5524; font-size: 17px; font-weight: 600; padding: 4px 0; }
            QGroupBox { background: white; border: 1px solid #e6ddd1;
                border-radius: 10px; margin-top: 10px; padding: 16px 12px 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
            QPushButton { background: #fff4e5; border: 1px solid #e7c79f;
                border-radius: 6px; padding: 8px 12px; }
            QPushButton:hover { background: #ffe4bd; }
            QPushButton:pressed { background: #f5d2a2; }
            QPushButton:disabled, QCheckBox:disabled { color: #aaa39b; }
            QComboBox { padding: 5px; border: 1px solid #d9cec1; border-radius: 4px; }
            QSlider::groove:horizontal { height: 5px; background: #e9e1d7; border-radius: 2px; }
            QSlider::handle:horizontal { background: #c7823f; width: 16px; margin: -5px 0;
                border-radius: 7px; }
        ''')
        controller.changed.connect(self.refresh)
        self.refresh()

    def add_slider(self, form, label, key, suffix):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(*LIMITS[key])
        slider.setAccessibleName(label)
        number = QLabel()
        number.setMinimumWidth(88 if key == 'speed' else 48)
        layout.addWidget(slider, 1)
        layout.addWidget(number)
        form.addRow(label, row)
        self.sliders[key] = (slider, number, suffix)
        slider.valueChanged.connect(lambda value: self.controller.set_preference(key, value))

    def add_check(self, form, label, key):
        check = QCheckBox(label)
        check.toggled.connect(lambda value: self.controller.set_preference(key, value))
        form.addRow(check)
        self.checks[key] = check

    def refresh(self):
        preferences = self.controller.preferences
        self.status_label.setText('●  ' + self.controller.pet.status_text())
        self.visibility_button.setText('隐藏宠物' if self.controller.pet.desired_visible() else '显示宠物')
        self.pause_button.setText('继续走动' if preferences.paused else '暂停走动')
        self.pause_button.setEnabled(not preferences.quiet and preferences.random_movement)
        self.jump_button.setEnabled(self.controller.pet.desired_visible())
        self.behavior_hint.setText('暂停只停止自主移动；眨眼、拖动和手动跳跃仍可使用。')
        for key, (slider, number, suffix) in self.sliders.items():
            blocker = QSignalBlocker(slider)
            slider.setValue(getattr(preferences, key))
            number.setText(str(getattr(preferences, key)) + suffix)
            del blocker
        for key, check in self.checks.items():
            blocker = QSignalBlocker(check)
            check.setChecked(getattr(preferences, key))
            del blocker
        blocker = QSignalBlocker(self.activity)
        self.activity.setCurrentText(preferences.activity)
        del blocker
        for key in ('random_movement', 'greeting'):
            self.checks[key].setEnabled(not preferences.quiet)
        self.save_label.setText('设置保存失败，请检查配置目录是否可写。' if self.controller.storage_error
                                else '设置自动保存，修改立即生效。')
        self.close_hint.setText('关闭此窗口后，yuki继续运行；点击系统托盘图标可重新打开。'
                                if self.controller.tray_available
                                else '当前系统托盘不可用；关闭窗口会将控制台最小化，方便重新打开。')

    def confirm_reset(self):
        answer = QMessageBox.question(
            self, '恢复默认设置', '恢复全部偏好并将yuki移回主屏幕底部？\n宠物素材不会被删除。',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.controller.reset_defaults()

    def closeEvent(self, event):
        if self.controller.shutting_down:
            event.accept()
            return
        event.ignore()
        if self.controller.tray_available:
            self.hide()
        else:
            self.showMinimized()
