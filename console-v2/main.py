"""小橘桌面宠物：宠物、控制台和系统托盘共用一个应用。"""
import argparse
from dataclasses import asdict
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from console import ControlWindow
from pet import DesktopPet, make_pet_icon
from settings_model import SettingsStore, normalize, Preferences
from icon_sleep import IconSleep
from edge_attachment import EdgeAttachment


class PetApplication(QObject):
    changed = Signal()

    def __init__(self, app, store=None, enable_tray=True, create_console=True):
        super().__init__(app)
        self.app = app
        self.store = store or SettingsStore()
        self.preferences = self.store.load()
        self.storage_error = False
        self.shutting_down = False
        self.saved_position = None
        self.pet = DesktopPet(self.preferences)
        self.pet.controller = self
        self.icon_sleep = IconSleep(self.pet, self.store)
        self.edge_attachment = EdgeAttachment(self.pet, self.store, self.icon_sleep)
        self.icon = make_pet_icon()
        self.app.setWindowIcon(self.icon)
        position = self.store.position()
        if position is not None:
            self.pet.move(position)
            self.pet.clamp_to_screen()
        self.pet.state_changed.connect(self.changed)
        self.pet.position_settled.connect(self.save_position)

        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip('小橘 · 桌面宠物')
        self.tray_available = enable_tray and QSystemTrayIcon.isSystemTrayAvailable()
        self.window = ControlWindow(self) if create_console else None
        self.tray_menu = self.create_menu(self.window or self.pet)
        self.tray_menu.aboutToShow.connect(self.refresh_menus)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.changed.connect(self.refresh_menus)
        if self.tray_available:
            self.tray.show()

        self.save_timer = QTimer(self)
        self.save_timer.setInterval(2000)
        self.save_timer.timeout.connect(self.save_position)
        self.save_timer.start()
        self.app.aboutToQuit.connect(self.cleanup)
        for screen in self.app.screens():
            self.watch_screen(screen)
        self.app.screenAdded.connect(self.watch_screen)
        self.app.screenRemoved.connect(self.schedule_screen_check)

    def start(self):
        self.pet.show()
        self.open_console()

    def open_console(self):
        if self.window is None:
            return
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def set_preference(self, name, value):
        values = asdict(self.preferences)
        if name not in values:
            raise ValueError('Unknown preference: ' + name)
        values[name] = value
        self.preferences = normalize(values)
        self.pet.apply_preferences(self.preferences)
        self.storage_error = not self.store.save(self.preferences)
        self.save_position()
        self.changed.emit()

    def toggle_visibility(self):
        if self.pet.isVisible():
            self.pet.hide()
        else:
            self.pet.clamp_to_screen()
            self.pet.show()
        self.changed.emit()

    def toggle_pause(self):
        self.set_preference('paused', not self.preferences.paused)

    def reset_defaults(self):
        self.preferences = Preferences()
        self.pet.apply_preferences(self.preferences)
        self.pet.state.jump_started = None
        self.pet.state.message_until = 0
        self.pet.state.walking = False
        self.pet.go_home(primary=True)
        self.storage_error = not self.store.save(self.preferences)
        self.save_position()
        self.changed.emit()

    def create_menu(self, parent):
        menu = QMenu(parent)
        menu.addAction('打开控制台', self.open_console)
        visible = menu.addAction('隐藏宠物', self.toggle_visibility)
        visible.setObjectName('visibility')
        paused = menu.addAction('暂停走动', self.toggle_pause)
        paused.setObjectName('pause')
        jump = menu.addAction('跳一下', self.pet.animator.jump)
        jump.setObjectName('jump')
        menu.addAction('回到桌面底部', self.pet.go_home)
        menu.addAction('停止图标互动 / 边缘附着', self.pet.wake_icon_sleep)
        menu.addSeparator()
        menu.addAction('退出小橘', self.quit)
        self.update_menu(menu)
        return menu

    def update_menu(self, menu):
        for action in menu.actions():
            if action.objectName() == 'visibility':
                action.setText('隐藏宠物' if self.pet.isVisible() else '显示宠物')
            elif action.objectName() == 'pause':
                action.setText('继续走动' if self.preferences.paused else '暂停走动')
                action.setEnabled(not self.preferences.quiet and self.preferences.random_movement)
            elif action.objectName() == 'jump':
                action.setEnabled(self.pet.isVisible())

    def refresh_menus(self):
        self.update_menu(self.tray_menu)
        self.tray.setToolTip('小橘 · ' + self.pet.status_text())

    def on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger,
                      QSystemTrayIcon.ActivationReason.DoubleClick):
            self.open_console()

    def watch_screen(self, screen):
        screen.availableGeometryChanged.connect(self.schedule_screen_check)
        screen.geometryChanged.connect(self.schedule_screen_check)
        self.schedule_screen_check()

    def schedule_screen_check(self, *_):
        QTimer.singleShot(0, self.adjust_screen)

    def adjust_screen(self):
        if not self.shutting_down:
            self.pet.wake_icon_sleep()
            self.pet.clamp_to_screen()
            self.save_position()

    def save_position(self):
        position = self.pet.pos()
        if position != self.saved_position:
            success = self.store.save_position(position)
            if success:
                self.saved_position = position
            else:
                self.storage_error = True
                self.changed.emit()

    def cleanup(self):
        if self.shutting_down:
            return
        self.shutting_down = True
        self.save_timer.stop()
        self.edge_attachment.cleanup()
        self.icon_sleep.cleanup()
        self.pet.animator.timer.stop()
        self.store.save(self.preferences)
        self.save_position()
        self.tray.hide()
        self.pet.hide()
        if self.window is not None:
            self.window.hide()

    def quit(self):
        self.cleanup()
        self.app.quit()


def main():
    parser = argparse.ArgumentParser(description='小橘桌面宠物与控制台')
    parser.add_argument('--smoke-test', action='store_true', help='启动后自动退出')
    parser.add_argument('--settings-file', help='指定独立配置文件，适合测试')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setOrganizationName('XiaoJu')
    app.setApplicationName('DesktopPet')
    app.setApplicationDisplayName('小橘 · 桌面宠物')
    app.setQuitOnLastWindowClosed(False)
    controller = PetApplication(app, SettingsStore(args.settings_file))
    controller.start()
    if args.smoke_test:
        controller.pet.animator.jump()
        QTimer.singleShot(800, controller.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
