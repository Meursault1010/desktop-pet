"""yuki桌面宠物：宠物、控制台和系统托盘共用一个应用。"""
import argparse
from dataclasses import asdict
import sys

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from console import ControlWindow
from pet import DesktopPet, make_pet_icon
from settings_model import SettingsStore, normalize, Preferences
from icon_sleep import IconSleep
from edge_attachment import EdgeAttachment
from pet_menu import CompanionMenu
from pet_patrol import Patrol
from pet_music import MusicCompanion


class PetApplication(QObject):
    changed = Signal()

    def __init__(self, app, store=None, enable_tray=True, create_console=True):
        super().__init__(app)
        self.app = app
        self.store = store or SettingsStore()
        self.preferences = self.store.load()
        self.storage_error = False
        self.shutting_down = False
        self.exit_requested = False
        self.quick_draft = ''
        self.quick_pending = None
        self.quick_last_text = ''
        self.saved_position = None
        self.pet = DesktopPet(self.preferences)
        self.pet.controller = self
        self.icon_sleep = IconSleep(self.pet, self.store)
        self.edge_attachment = EdgeAttachment(self.pet, self.store, self.icon_sleep)
        # Warm bounds and static pose pixmaps before the first drag, not inside
        # a mouse-move handler. Preview uses these static images directly.
        self.icon_sleep.load_poses()
        from icon_sleep import GEOMETRIES
        from locomotion import frames
        for side in GEOMETRIES:self.icon_sleep.pose_pixmap(side,0)
        for name in ('walk-left','walk-right','climb-left','climb-right','hang'):frames(name)
        self.pet.snap_preview.request_surfaces()
        self.patrol = Patrol(self.pet, self.icon_sleep, self.store)
        self.pet.state.patrol = self.patrol
        self.music = MusicCompanion(self.pet)
        self.pet.state.music = self.music
        self.icon = make_pet_icon()
        self.app.setWindowIcon(self.icon)
        position = self.store.position()
        if position is not None:
            self.pet.move(position)
            self.pet.clamp_to_screen()
        self.pet.state_changed.connect(self.changed)
        self.pet.position_settled.connect(self.save_position)

        self.tray = QSystemTrayIcon(self.icon, self)
        self.tray.setToolTip('yuki · 桌面宠物')
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
        self.pet.present(True)
        self.music.start()
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
        if self.exit_requested:
            return
        self.pet.present(not self.pet.desired_visible())
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
        menu = CompanionMenu(parent, self.icon)
        menu.quick_chat(self)
        menu.addSeparator()
        menu.command('console', '打开工作台', self.open_console, 'console')
        menu.addSeparator()
        menu.command('visibility', '隐藏宠物', self.toggle_visibility, 'visibility')
        menu.command('pause', '暂停走动', self.toggle_pause, 'pause')
        menu.command('quiet', '安静陪伴', lambda checked: self.set_preference('quiet', checked), checkable=True)
        menu.command('auto_snap', '拖放即时吸附', lambda checked: self.set_preference('auto_snap', checked), checkable=True)
        menu.addSeparator()
        menu.command('home', '回到桌面底部', self.pet.go_home, 'home')
        menu.command('detach', '离开停靠处', self.pet.wake_icon_sleep, 'detach')
        menu.addSeparator()
        # PetService redirects the last action through Electron's exit handler.
        menu.command('exit', '退出 yuki', self.quit, 'exit')
        self.update_menu(menu)
        menu.aboutToShow.connect(lambda: self.update_menu(menu))
        return menu

    def update_menu(self, menu):
        if isinstance(menu, CompanionMenu):
            menu.status.setText(self.pet.status_text())
            menu.routine.setText(self.pet.state.routine.period['name'])
            menu.update_chat(self)
        for action in menu.actions():
            if action.objectName() == 'visibility':
                action.setText('隐藏宠物' if self.pet.desired_visible() else '显示宠物')
            elif action.objectName() == 'pause':
                action.setText('继续走动' if self.preferences.paused else '暂停走动')
                action.setEnabled(not self.preferences.quiet and self.preferences.random_movement)
            elif action.objectName() in ('quiet', 'auto_snap'):
                action.setChecked(getattr(self.preferences, action.objectName()))
            elif action.objectName() in ('home', 'detach'):
                action.setEnabled(self.pet.desired_visible())

    def refresh_menus(self):
        self.update_menu(self.tray_menu)
        self.tray.setToolTip('yuki · ' + self.pet.status_text())

    def quick_chat_send(self, text):
        self.pet.bubble.say('请使用 Electron 版 yuki 连接本地模型聊天。', 'error')
        return False

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
        if self.pet.state.physics.active or self.pet.drag_origin is not None:
            return
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
        self.pet.snap_preview.shutdown()
        self.music.cleanup()
        self.edge_attachment.cleanup()
        self.icon_sleep.cleanup()
        self.pet.animator.timer.stop()
        self.pet.bubble.timer.stop()
        self.pet.bubble.clear()
        self.store.save(self.preferences)
        self.save_position()
        self.tray.hide()
        self.pet.hide()
        if self.window is not None:
            self.window.hide()

    def quit(self):
        if self.exit_requested:
            return
        self.exit_requested = True
        if self.pet.isVisible():
            self.pet.present(False)
            delay = round(self.pet.presence.duration*1000)+50
            QTimer.singleShot(delay, self.finish_quit)
        else:
            self.finish_quit()

    def finish_quit(self):
        self.cleanup()
        self.app.quit()


def main():
    parser = argparse.ArgumentParser(description='yuki桌面宠物与控制台')
    parser.add_argument('--smoke-test', action='store_true', help='启动后自动退出')
    parser.add_argument('--settings-file', help='指定独立配置文件，适合测试')
    args = parser.parse_args()
    app = QApplication(sys.argv[:1])
    app.setOrganizationName('XiaoJu')
    app.setApplicationName('DesktopPet')
    app.setApplicationDisplayName('yuki · 桌面宠物')
    app.setQuitOnLastWindowClosed(False)
    controller = PetApplication(app, SettingsStore(args.settings_file))
    controller.start()
    if args.smoke_test:
        controller.pet.animator.jump()
        QTimer.singleShot(800, controller.quit)
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
